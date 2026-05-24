"""Patch engine for managing resume modifications and patches."""

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class PatchEngine:
    """Manages patches and current document state."""

    def __init__(self, initial_text: str):
        self.current_text = initial_text
        self._applied_log: Dict[str, Dict[str, Any]] = {}
        self._pending_replacements: Dict[str, List[str]] = {}

    def apply_patch(
        self,
        patch_id: str,
        original_text: str,
        replacement_text: str,
    ) -> bool:
        """Apply a patch to the current document state."""
        if original_text not in self.current_text:
            logger.warning(f"Patch {patch_id}: original text not found in document")
            return False

        self.current_text = self.current_text.replace(original_text, replacement_text)
        self._applied_log[patch_id] = {
            "original": original_text,
            "replacement": replacement_text,
        }
        self._pending_replacements[patch_id] = [replacement_text]
        return True

    def add_bullet(
        self,
        section: str,
        bullet: str,
        placement: str = "start",
    ) -> bool:
        """Add a coaching bullet to a section."""
        # Simple heuristic: find the section and add the bullet
        lines = self.current_text.split("\n")
        section_idx = -1

        # Find section header (simplified)
        for i, line in enumerate(lines):
            if section.lower() in line.lower():
                section_idx = i
                break

        if section_idx == -1:
            logger.warning(f"Section '{section}' not found")
            return False

        # Find next non-empty line after header
        insert_idx = section_idx + 1
        while insert_idx < len(lines) and not lines[insert_idx].strip():
            insert_idx += 1

        # Insert bullet
        if placement == "start":
            lines.insert(insert_idx, bullet)
        else:
            lines.append(bullet)

        self.current_text = "\n".join(lines)
        return True

    def verify_document_integrity(
        self,
        applied_patch_ids: Optional[List[str]] = None,
        applied_bullets: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Verify that all applied patches and bullets are in current text.
        """
        current = self.current_text
        missing_patches: List[str] = []
        missing_bullets: List[str] = []

        # Check patches
        for patch_id, snapshot in self._applied_log.items():
            if patch_id.startswith("coaching_"):
                continue
            replacements = self._pending_replacements.get(patch_id, [])
            for rep in replacements:
                if rep and rep not in current:
                    missing_patches.append(patch_id)

        # Check bullets
        for bullet in applied_bullets or []:
            clean = bullet.strip("• ").strip()
            if clean and clean not in current:
                missing_bullets.append(bullet[:60])

        total_applied = len(self._applied_log) + len(applied_bullets or [])
        total_verified = total_applied - len(missing_patches) - len(missing_bullets)

        return {
            "clean": len(missing_patches) == 0 and len(missing_bullets) == 0,
            "missing_patches": missing_patches,
            "missing_bullets": missing_bullets,
            "total_applied": total_applied,
            "total_verified": max(total_verified, 0),
        }


# Global session-based patch engines
_patch_engines: Dict[str, PatchEngine] = {}


def get_or_create_engine(session_id: str, initial_text: str) -> PatchEngine:
    """Get existing patch engine or create new one."""
    if session_id not in _patch_engines:
        _patch_engines[session_id] = PatchEngine(initial_text)
    return _patch_engines[session_id]


def get_engine(session_id: str) -> Optional[PatchEngine]:
    """Get existing patch engine if any patches applied."""
    return _patch_engines.get(session_id)
