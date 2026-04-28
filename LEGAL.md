# Legal Notice

## Responsible Use

OGI (OpenGraph Intel) is a general-purpose, open-source tool for visual link analysis and OSINT research. The authors make no representations about the suitability of this software for any particular purpose.

**You are solely responsible for how you use OGI and any data you collect, process, or store with it.**

---

## Third-Party Terms of Service

OGI includes transforms that make automated requests to external services (DNS resolvers, WHOIS databases, certificate transparency logs, public websites, social media platforms, etc.).

Many of these services have Terms of Service that restrict automated or bulk access. Before using any transform against an external service, it is your responsibility to:

1. Read and comply with that service's Terms of Service and acceptable use policy.
2. Obtain any required authorization before querying systems you do not own.
3. Respect rate limits, robots.txt directives, and any other access controls.

Unauthorized automated access to third-party systems may constitute a violation of their ToS, and in some jurisdictions may have legal consequences (e.g., under the Computer Fraud and Abuse Act in the US, or equivalent legislation elsewhere).

---

## Data Protection and Privacy (GDPR and Beyond)

OGI can collect, enrich, and display personal data (names, email addresses, phone numbers, IP addresses, social media profiles, organizational roles, etc.).

If you are subject to the EU General Data Protection Regulation (GDPR) or similar data protection law:

- **You are the data controller.** OGI is a tool you operate; it does not independently determine the purposes or means of processing. You bear full responsibility for ensuring your use is lawful.
- **Establish a lawful basis** before collecting or processing personal data. Common bases include legitimate interest, legal obligation, or explicit consent.
- **Minimize data collection.** Collect only what you need for a specific, documented purpose.
- **Respect data subject rights.** Individuals have rights to access, correct, erase, and port their data. Ensure your workflows allow you to honor these requests.
- **Secure your data.** Take appropriate technical and organizational measures to protect personal data you collect with OGI.
- **Do not store personal data indefinitely.** Establish and follow a retention policy.

OGI itself stores data only within your own deployment (local SQLite or your own PostgreSQL instance). No data is transmitted to the OGI project authors.

---

## No Affiliation with Third-Party Trademarks

OGI supports import of the MTGX graph exchange file format for interoperability purposes. This does not imply any affiliation, partnership, sponsorship, or endorsement by the owners of tools or trademarks associated with that format.

Any other third-party product names, trademarks, or service names mentioned in this project are used for descriptive or identification purposes only. Their use does not imply affiliation with or endorsement by their respective owners.

---

## Disclaimer of Warranties

OGI is provided "AS IS" without warranty of any kind, express or implied, including but not limited to the warranties of merchantability, fitness for a particular purpose, and non-infringement. In no event shall the authors or copyright holders be liable for any claim, damages, or other liability arising from the use of the software.

---

## License

OGI is licensed under the [GNU Affero General Public License v3.0](LICENSE). Transforms, plugins, and community contributions may carry their own licenses — check each component's license before use.
