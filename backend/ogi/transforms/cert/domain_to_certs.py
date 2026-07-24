import asyncio
import socket
import ssl

from ogi.models import Entity, EntityType, Edge, TransformResult
from ogi.transforms.base import BaseTransform, TransformConfig


def _fetch_certificate(domain: str) -> dict[str, str | list[tuple[str, str]]]:
    """Connect to domain:443 and retrieve the SSL certificate as a parsed dict."""
    ctx = ssl.create_default_context()
    with ctx.wrap_socket(socket.socket(socket.AF_INET), server_hostname=domain) as sock:
        sock.settimeout(10)
        sock.connect((domain, 443))
        cert = sock.getpeercert()
    if cert is None:
        raise RuntimeError("No certificate returned by the server")
    return cert


def _extract_field(field_tuples: tuple[tuple[tuple[str, str], ...], ...], key: str) -> str:
    """Extract a value from the nested tuple structure of issuer/subject fields."""
    for rdn in field_tuples:
        for attr_name, attr_value in rdn:
            if attr_name == key:
                return attr_value
    return ""


class DomainToCerts(BaseTransform):
    name = "domain_to_certs"
    display_name = "Domain to SSL Certificates"
    description = "Retrieves the SSL/TLS certificate for a domain and extracts certificate details"
    input_types = [EntityType.DOMAIN]
    output_types = [EntityType.SSL_CERTIFICATE, EntityType.ORGANIZATION]
    category = "Certificate"
    long_description = (
        "Opens a TLS connection to the domain on port 443 over IPv4 with a ten "
        "second timeout and reads the certificate the server presents. The "
        "connection uses Python's default verifying SSL context, so the certificate "
        "must chain to a trusted root and match the requested host name. From the "
        "parsed certificate it creates a single SSLCertificate entity whose value is "
        "the subject common name, falling back to the domain itself, carrying the "
        "issuer and subject common names, their organisation names, the serial "
        "number, the notBefore and notAfter validity dates, and the full list of "
        "subject alternative names joined into one 'sans' property. The domain is "
        "linked to it with a 'secured by' edge. When the issuer's organisation name "
        "is present, an Organization entity is also created for the certificate "
        "authority and linked from the certificate with an 'issued by' edge. "
        "Timeouts, name resolution failures, refused connections and SSL errors are "
        "reported as result messages and return no entities."
    )
    when_to_use = (
        "Use to confirm what is actually being served on a host and who vouches for "
        "it. The subject and SAN list show which other names the same certificate "
        "covers, and the validity dates give a rough age for the deployment. Run "
        "Certificate Transparency Lookup alongside it to see historically issued "
        "certificates that a live connection cannot show, and take names from the "
        "SAN property forward with Domain to IP Address."
    )
    limitations = (
        "Because the default verifying context is used, self-signed, expired, "
        "hostname-mismatched or otherwise untrusted certificates raise an SSL error "
        "and produce no entity at all, which is often exactly the case an "
        "investigator cares about. Only the leaf certificate is captured, with no "
        "chain, public key or fingerprint. Connections are IPv4 and port 443 only, "
        "so IPv6-only hosts and TLS on other ports are invisible, and a host behind "
        "a CDN returns the CDN's certificate rather than the origin's. SANs are "
        "stored as one comma-joined string, not as separate entities."
    )
    example_use_cases = [
        "Check which other host names a target's live certificate covers via its SANs",
        "Identify the certificate authority an organisation uses across its estate",
        "Read certificate validity dates to estimate when a service was last redeployed",
    ]

    async def run(self, entity: Entity, config: TransformConfig) -> TransformResult:
        domain = entity.value
        entities: list[Entity] = []
        edges: list[Edge] = []
        messages: list[str] = []

        try:
            loop = asyncio.get_event_loop()
            cert = await loop.run_in_executor(None, _fetch_certificate, domain)

            # Extract subject and issuer details
            subject_tuples = cert.get("subject", ())
            issuer_tuples = cert.get("issuer", ())

            subject_cn = _extract_field(subject_tuples, "commonName")
            subject_org = _extract_field(subject_tuples, "organizationName")
            issuer_cn = _extract_field(issuer_tuples, "commonName")
            issuer_org = _extract_field(issuer_tuples, "organizationName")

            serial_number = cert.get("serialNumber", "")
            not_before = cert.get("notBefore", "")
            not_after = cert.get("notAfter", "")

            # Extract Subject Alternative Names
            san_entries: list[str] = []
            for san_type, san_value in cert.get("subjectAltName", ()):
                san_entries.append(san_value)
            sans = ", ".join(san_entries)

            # Build a display value for the certificate
            cert_value = subject_cn or domain

            cert_entity = Entity(
                type=EntityType.SSL_CERTIFICATE,
                value=cert_value,
                properties={
                    "issuer": issuer_cn,
                    "subject": subject_cn,
                    "serial_number": serial_number,
                    "not_before": not_before,
                    "not_after": not_after,
                    "sans": sans,
                    "issuer_org": issuer_org,
                    "subject_org": subject_org,
                },
                source=self.name,
            )
            entities.append(cert_entity)
            edges.append(Edge(
                source_id=entity.id,
                target_id=cert_entity.id,
                label="secured by",
                source_transform=self.name,
            ))
            messages.append(f"Certificate: {cert_value}")
            messages.append(f"Issuer: {issuer_cn}")
            messages.append(f"Valid: {not_before} - {not_after}")
            if sans:
                messages.append(f"SANs: {sans}")

            # Create an Organization entity for the issuer if available
            if issuer_org:
                org_entity = Entity(
                    type=EntityType.ORGANIZATION,
                    value=issuer_org,
                    properties={"role": "certificate_issuer", "issuer_cn": issuer_cn},
                    source=self.name,
                )
                entities.append(org_entity)
                edges.append(Edge(
                    source_id=cert_entity.id,
                    target_id=org_entity.id,
                    label="issued by",
                    source_transform=self.name,
                ))
                messages.append(f"Issuer Org: {issuer_org}")

        except socket.timeout:
            messages.append(f"Connection to {domain}:443 timed out")
        except socket.gaierror:
            messages.append(f"Could not resolve {domain}")
        except ssl.SSLError as e:
            messages.append(f"SSL error for {domain}: {e}")
        except ConnectionRefusedError:
            messages.append(f"Connection refused to {domain}:443")
        except Exception as e:
            messages.append(f"Error retrieving certificate for {domain}: {e}")

        return TransformResult(entities=entities, edges=edges, messages=messages)
