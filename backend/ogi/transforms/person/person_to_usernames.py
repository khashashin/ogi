import re
import unicodedata

from ogi.models import Entity, EntityType, Edge, TransformResult
from ogi.transforms.base import BaseTransform, TransformConfig


def _slug_token(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_only = normalized.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "", ascii_only.lower())


def _coerce_name_list(raw: object) -> list[str]:
    if isinstance(raw, str):
        return [raw]
    if isinstance(raw, list):
        return [item for item in raw if isinstance(item, str)]
    return []


class PersonToUsernames(BaseTransform):
    name = "person_to_usernames"
    display_name = "Person to Usernames"
    description = "Generates likely usernames from a person's name and aliases"
    input_types = [EntityType.PERSON]
    output_types = [EntityType.USERNAME]
    category = "People"

    def _candidate_names(self, entity: Entity) -> list[tuple[str, str]]:
        props = entity.properties or {}
        candidates: list[tuple[str, str]] = []

        first_name = str(props.get("first_name", "")).strip()
        last_name = str(props.get("last_name", "")).strip()
        display_name = str(props.get("display_name", "")).strip()
        aliases = _coerce_name_list(props.get("aliases"))

        if entity.value.strip():
            candidates.append((entity.value.strip(), "entity_value"))
        if display_name:
            candidates.append((display_name, "display_name"))
        if first_name and last_name:
            candidates.append((f"{first_name} {last_name}", "first_last_name"))
        candidates.extend((alias.strip(), "alias") for alias in aliases if alias.strip())

        return candidates

    def _generate_patterns(self, candidate_name: str) -> list[tuple[str, float, str]]:
        parts = [part for part in re.split(r"[\s._-]+", candidate_name.strip()) if part]
        if not parts:
            return []

        first = _slug_token(parts[0])
        last = _slug_token(parts[-1]) if len(parts) > 1 else ""
        middle_initial = _slug_token(parts[1])[0:1] if len(parts) > 2 and _slug_token(parts[1]) else ""

        base_tokens = [_slug_token(part) for part in parts]
        base_tokens = [token for token in base_tokens if token]
        if not base_tokens:
            return []

        results: list[tuple[str, float, str]] = []

        if len(base_tokens) == 1:
            token = base_tokens[0]
            if len(token) >= 3:
                results.append((token, 0.5, "derived_from_single_name"))
            return results

        full_joined = "".join(base_tokens)
        first_last = f"{first}{last}"
        first_dot_last = f"{first}.{last}"
        first_underscore_last = f"{first}_{last}"
        first_initial_last = f"{first[:1]}{last}"
        last_first_initial = f"{last}{first[:1]}"
        first_last_initial = f"{first}{last[:1]}"
        first_initial_middle_last = f"{first[:1]}{middle_initial}{last}" if middle_initial else ""

        patterns = [
            (first_last, 0.62, "derived_from_name_pattern:firstlast"),
            (first_dot_last, 0.6, "derived_from_name_pattern:first.last"),
            (first_underscore_last, 0.58, "derived_from_name_pattern:first_last"),
            (first_initial_last, 0.57, "derived_from_name_pattern:flast"),
            (last_first_initial, 0.54, "derived_from_name_pattern:lastf"),
            (first_last_initial, 0.52, "derived_from_name_pattern:firstl"),
            (full_joined, 0.5, "derived_from_name_pattern:fulljoined"),
        ]
        if first_initial_middle_last:
            patterns.append((first_initial_middle_last, 0.53, "derived_from_name_pattern:fmlast"))

        for username, confidence, rationale in patterns:
            if len(username) >= 3:
                results.append((username, confidence, rationale))
        return results

    async def run(self, entity: Entity, _config: TransformConfig) -> TransformResult:

        generated: dict[str, tuple[float, str]] = {}
        for raw_name, source in self._candidate_names(entity):
            for username, confidence, rationale in self._generate_patterns(raw_name):
                existing = generated.get(username)
                enriched_rationale = f"{rationale};source={source}"
                if existing is None or confidence > existing[0]:
                    generated[username] = (confidence, enriched_rationale)

        entities: list[Entity] = []
        edges: list[Edge] = []
        for username, (confidence, rationale) in sorted(
            generated.items(),
            key=lambda item: (-item[1][0], item[0]),
        )[:10]:
            username_entity = Entity(
                type=EntityType.USERNAME,
                value=username,
                properties={
                    "username": username,
                    "confidence": round(confidence, 2),
                    "rationale": rationale,
                },
                source=self.name,
            )
            entities.append(username_entity)
            edges.append(Edge(
                source_id=entity.id,
                target_id=username_entity.id,
                label="possible username",
                source_transform=self.name,
            ))

        messages: list[str]
        if entities:
            messages = [f"Generated {len(entities)} likely username candidates."]
        else:
            messages = ["Not enough person name data to derive username candidates."]

        return TransformResult(entities=entities, edges=edges, messages=messages)
