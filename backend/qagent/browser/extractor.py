from typing import List, Dict, Any, Optional
import re
from qagent.domain.schemas import CandidateAction, BoundingRect



EXTRACTOR_JS = """
() => {
    const candidates = [];
    let id = 1;
    const interactableSelectors = 'button, a, input, select, textarea, [role="button"], [role="link"], [role="tab"]';
    const elements = Array.from(document.querySelectorAll(interactableSelectors));

    for (const el of elements) {
        if (id > 40) break;
        const rect = el.getBoundingClientRect();
        const style = window.getComputedStyle(el);
        if (style.display === 'none' || style.visibility === 'hidden' || style.opacity === '0') continue;
        if (rect.width === 0 && rect.height === 0) continue;

        let label = (el.innerText || el.getAttribute('aria-label') || el.getAttribute('placeholder') || el.getAttribute('value') || el.getAttribute('title') || '').trim();
        if (!label && el.tagName.toLowerCase() === 'input') {
            label = el.getAttribute('name') || el.getAttribute('id') || 'Input field';
        }

        // Build unique or simple selector
        let sel = el.tagName.toLowerCase();
        if (el.id) {
            sel = `#${el.id}`;
        } else if (el.getAttribute('data-testid')) {
            sel = `[data-testid="${el.getAttribute('data-testid')}"]`;
        } else if (el.className && typeof el.className === 'string') {
            const firstClass = el.className.split(' ').filter(c => c && !c.includes(':'))[0];
            if (firstClass) sel += `.${firstClass}`;
        }

        candidates.push({
            id: id++,
            tag: el.tagName.toLowerCase(),
            selector: sel,
            label: label.substring(0, 80),
            action_type: el.tagName.toLowerCase() === 'input' && (el.type === 'text' || el.type === 'password' || el.type === 'email') ? 'fill' : 'click',
            value: el.value || null,
            bounding_box: {
                x: rect.x,
                y: rect.y,
                width: rect.width,
                height: rect.height
            }
        });
    }
    return candidates;
}
"""


def extract_candidates_from_html(html: str, max_candidates: int = 40) -> List[CandidateAction]:
    """
    Offline/static HTML candidate extractor for tests and fallback.
    Extracts up to 40 interactive candidates.
    """
    candidates: List[CandidateAction] = []
    # Simple regex / soup parse
    pattern = re.compile(r'<(button|a|input)[^>]*>(.*?)</\1>|<(input)[^>]*/>|<(input)[^>]*>', re.IGNORECASE | re.DOTALL)
    cid = 1
    
    for match in pattern.finditer(html):
        if cid > max_candidates:
            break
        tag = (match.group(1) or match.group(3) or match.group(4) or "button").lower()
        full_match = match.group(0)
        
        # Label extraction
        label_match = re.search(r'>([^<]+)<', full_match)
        label = label_match.group(1).strip() if label_match else ""
        if not label:
            val_match = re.search(r'value=["\']([^"\']+)["\']', full_match)
            label = val_match.group(1) if val_match else f"{tag.capitalize()} element"

        testid_match = re.search(r'data-testid=["\']([^"\']+)["\']', full_match)
        id_match = re.search(r'id=["\']([^"\']+)["\']', full_match)
        if testid_match:
            sel = f'[data-testid="{testid_match.group(1)}"]'
        elif id_match:
            sel = f'#{id_match.group(1)}'
        else:
            sel = tag

        action_type = "fill" if tag == "input" else "click"
        candidates.append(CandidateAction(
            id=cid,
            tag=tag,
            selector=sel,
            label=label,
            action_type=action_type,
            bounding_box=BoundingRect(x=0.0, y=0.0, width=100.0, height=30.0),
        ))
        cid += 1

    return candidates
