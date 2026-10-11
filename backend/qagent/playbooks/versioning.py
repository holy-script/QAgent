import hashlib
import json
from typing import Any, Dict, Optional, Tuple

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from qagent.domain.models import ItemLink, Playbook, PlaybookItem, PlaybookVersion


async def store_version(session: AsyncSession, playbook: Playbook, raw_markdown: str,
                        parsed: Dict[str, Any], version_id: Optional[str] = None) -> Tuple[PlaybookVersion, bool]:
    """
    Stores a new version unless the content hash matches the latest one. Items and their links are
    written alongside so traceability queries need no re-parsing. Returns (version, created).
    """
    versions = (await session.execute(
        select(PlaybookVersion).where(PlaybookVersion.playbook_id == playbook.id)
        .order_by(PlaybookVersion.version_no)
    )).scalars().all()
    latest = versions[-1] if versions else None
    if latest is not None and latest.content_hash == parsed["content_hash"]:
        playbook.current_version_id = latest.id
        return latest, False

    kwargs = {"id": version_id} if version_id else {}
    version = PlaybookVersion(
        playbook_id=playbook.id, version_no=(latest.version_no + 1) if latest else 1, raw_markdown=raw_markdown,
        parsed=parsed, warnings=parsed["warnings"], content_hash=parsed["content_hash"], **kwargs,
    )
    session.add(version)
    await session.flush()
    for item in parsed["items"]:
        session.add(PlaybookItem(
            version_id=version.id, item_key=item["key"], category=item["category"], title=item["title"],
            body=item["body"], content_hash=hashlib.sha256(
                json.dumps(item, sort_keys=True, default=str).encode()).hexdigest(),
        ))
    for link in parsed["links"]:
        session.add(ItemLink(version_id=version.id, **link))
    playbook.current_version_id = version.id
    return version, True
