from __future__ import annotations

from piespector.domain.editor import TAB_ENV
from piespector.domain.modes import MODE_ENV_EDIT, MODE_ENV_SELECT, MODE_NORMAL


class EnvStateMixin:
    def ensure_env_workspace(self) -> None:
        if not self.env_names:
            self.env_names = ["Default"]
        if not self.env_sets:
            self.env_sets = {"Default": {}}
        for name in list(self.env_names):
            self.env_sets.setdefault(name, {})
        self.env_names = [name for name in self.env_names if name in self.env_sets]
        if not self.env_names:
            self.env_names = ["Default"]
            self.env_sets = {"Default": {}}
        if self.selected_env_name not in self.env_sets:
            self.selected_env_name = self.env_names[0]
        self.env_pairs = self.env_sets[self.selected_env_name]

    def active_env_label(self) -> str:
        self.ensure_env_workspace()
        return self.selected_env_name

    def select_env_set(self, step: int) -> None:
        self.ensure_env_workspace()
        if not self.env_names:
            return
        current_index = (
            self.env_names.index(self.selected_env_name)
            if self.selected_env_name in self.env_names
            else 0
        )
        self.selected_env_name = self.env_names[
            (current_index + step) % len(self.env_names)
        ]
        self.env_pairs = self.env_sets[self.selected_env_name]
        self.selected_env_index = 0
        self.env_scroll_offset = 0
        self.selected_env_field_index = 0
        self.env_creating_new = False
        self.message = f"Selected env {self.selected_env_name}."
        self.notify_env_mutated()

    def create_env_set(self, name: str) -> bool:
        self.ensure_env_workspace()
        env_name = name.strip()
        if not env_name:
            self.message = "Name cannot be empty."
            return False
        if env_name in self.env_sets:
            self.message = f"Env {env_name} already exists."
            return False
        self.env_names.append(env_name)
        self.env_sets[env_name] = {}
        self.selected_env_name = env_name
        self.env_pairs = self.env_sets[env_name]
        self.selected_env_index = 0
        self.env_scroll_offset = 0
        self.mode = MODE_NORMAL
        self.message = f"Created env {env_name}."
        self.notify_env_mutated()
        return True

    def rename_selected_env_set(self, name: str) -> bool:
        self.ensure_env_workspace()
        old_name = self.selected_env_name
        new_name = name.strip()
        if not new_name:
            self.message = "Name cannot be empty."
            return False
        if new_name == old_name:
            self.message = f"Renamed env {new_name}."
            return True
        if new_name in self.env_sets:
            self.message = f"Env {new_name} already exists."
            return False
        pairs = self.env_sets.pop(old_name, {})
        self.env_sets[new_name] = pairs
        self.env_names = [new_name if item == old_name else item for item in self.env_names]
        self.selected_env_name = new_name
        self.env_pairs = pairs
        self.message = f"Renamed env {new_name}."
        self.notify_env_mutated()
        return True

    def delete_selected_env_set(self) -> bool:
        self.ensure_env_workspace()
        if len(self.env_names) <= 1:
            self.message = "At least one env must remain."
            return False
        env_name = self.selected_env_name
        current_index = self.env_names.index(env_name)
        self.env_names = [name for name in self.env_names if name != env_name]
        self.env_sets.pop(env_name, None)
        self.selected_env_name = self.env_names[min(current_index, len(self.env_names) - 1)]
        self.env_pairs = self.env_sets[self.selected_env_name]
        self.selected_env_index = 0
        self.env_scroll_offset = 0
        self.selected_env_field_index = 0
        self.env_creating_new = False
        self.mode = MODE_NORMAL
        self.message = f"Deleted env {env_name}."
        self.notify_env_mutated()
        return True

    def import_env_sets(
        self,
        env_names: list[str],
        env_sets: dict[str, dict[str, str]],
    ) -> int:
        self.ensure_env_workspace()
        if not env_names:
            self.message = "No envs found in import file."
            return 0

        used_names = {name.strip().lower() for name in self.env_names}
        imported_names: list[str] = []
        for original_name in env_names:
            pairs = env_sets.get(original_name, {})
            unique_name = self._unique_env_set_name(original_name, used_names)
            self.env_names.append(unique_name)
            self.env_sets[unique_name] = dict(pairs)
            imported_names.append(unique_name)

        if not imported_names:
            self.message = "No envs found in import file."
            return 0

        self.selected_env_name = imported_names[0]
        self.env_pairs = self.env_sets[self.selected_env_name]
        self.selected_env_index = 0
        self.env_scroll_offset = 0
        self.selected_env_field_index = 0
        self.env_creating_new = False
        self.current_tab = TAB_ENV
        self.mode = MODE_NORMAL
        self.message = (
            f"Imported {len(imported_names)} env."
            if len(imported_names) == 1
            else f"Imported {len(imported_names)} envs."
        )
        self.notify_env_mutated()
        return len(imported_names)

    def _unique_env_set_name(self, base_name: str, used_names: set[str]) -> str:
        candidate = base_name.strip() or "Imported"
        normalized = candidate.lower()
        if normalized not in used_names:
            used_names.add(normalized)
            return candidate

        suffix = " Import"
        numbered = 1
        while True:
            proposed = (
                f"{candidate}{suffix}"
                if numbered == 1
                else f"{candidate}{suffix} {numbered}"
            )
            normalized = proposed.lower()
            if normalized not in used_names:
                used_names.add(normalized)
                return proposed
            numbered += 1

    def get_env_items(self) -> list[tuple[str, str]]:
        self.ensure_env_workspace()
        return list(self.env_pairs.items())

    def clamp_selected_env_index(self) -> None:
        items = self.get_env_items()
        if not items:
            self.selected_env_index = 0
            return
        self.selected_env_index = max(0, min(self.selected_env_index, len(items) - 1))

    def clamp_env_scroll_offset(self, visible_rows: int) -> None:
        item_count = len(self.get_env_items())
        max_offset = max(item_count - max(visible_rows, 1), 0)
        self.env_scroll_offset = max(0, min(self.env_scroll_offset, max_offset))

    def select_env_row(self, step: int) -> None:
        items = self.get_env_items()
        if not items:
            self.selected_env_index = 0
            return
        self.selected_env_index = (self.selected_env_index + step) % len(items)

    def ensure_env_selection_visible(self, visible_rows: int) -> None:
        self.clamp_selected_env_index()
        if self.selected_env_index < self.env_scroll_offset:
            self.env_scroll_offset = self.selected_env_index
        elif self.selected_env_index >= self.env_scroll_offset + visible_rows:
            self.env_scroll_offset = self.selected_env_index - visible_rows + 1
        self.clamp_env_scroll_offset(visible_rows)

    def scroll_env_window(self, step: int, visible_rows: int) -> None:
        self.env_scroll_offset += step
        self.clamp_env_scroll_offset(visible_rows)

    def enter_env_select_mode(self) -> None:
        self.ensure_env_workspace()
        self.current_tab = TAB_ENV
        self.mode = MODE_ENV_SELECT
        self.selected_env_field_index = 0
        self.env_creating_new = False
        self.message = "h/l fields, e edit, d delete, Esc back."
        self.clamp_selected_env_index()

    def cycle_env_field(self, step: int) -> None:
        self.selected_env_field_index = (self.selected_env_field_index + step) % 2

    def selected_env_field(self) -> tuple[str, str]:
        if self.selected_env_field_index == 0:
            return ("key", "Key")
        return ("value", "Value")

    def enter_env_edit_mode(self) -> None:
        item = self.get_selected_env_item()
        if item is None:
            self.message = "Nothing to edit."
            self.mode = MODE_NORMAL
            return
        self.mode = MODE_ENV_EDIT
        self.message = ""

    def enter_env_create_mode(self) -> None:
        self.ensure_env_workspace()
        self.current_tab = TAB_ENV
        self.mode = MODE_ENV_EDIT
        self.selected_env_field_index = 0
        self.env_creating_new = True
        self.message = ""

    def leave_env_edit_mode(self) -> None:
        self.mode = MODE_ENV_SELECT
        self.env_creating_new = False
        self.message = "h/l fields, e edit, d delete, Esc back."

    def leave_env_interaction(self) -> None:
        self.mode = MODE_NORMAL
        self.selected_env_field_index = 0
        self.env_creating_new = False

    def get_selected_env_item(self) -> tuple[str, str] | None:
        items = self.get_env_items()
        if not items:
            return None
        self.clamp_selected_env_index()
        return items[self.selected_env_index]

    def save_selected_env_field(self, value: str | None = None) -> str | None:
        self.ensure_env_workspace()
        field_name, field_label = self.selected_env_field()
        raw = value or ""
        if self.env_creating_new:
            if field_name != "key":
                return None
            new_key = raw.strip()
            if not new_key:
                self.message = "Key cannot be empty."
                return None
            if new_key in self.env_pairs:
                self.message = f"Key {new_key} already exists."
                return None
            self.env_pairs[new_key] = ""
            self.env_sets[self.selected_env_name] = self.env_pairs
            self.selected_env_index = max(0, len(self.env_pairs) - 1)
            self.selected_env_field_index = 1
            self.env_creating_new = False
            self.mode = MODE_ENV_EDIT
            self.message = ""
            self.notify_env_mutated()
            return new_key

        item = self.get_selected_env_item()
        if item is None:
            return None
        key, existing_value = item
        if field_name == "key":
            new_key = raw.strip()
            if not new_key:
                self.message = "Key cannot be empty."
                return None
            if new_key != key and new_key in self.env_pairs:
                self.message = f"Key {new_key} already exists."
                return None
            items = self.get_env_items()
            items[self.selected_env_index] = (new_key, existing_value)
            self.env_pairs = dict(items)
            self.env_sets[self.selected_env_name] = self.env_pairs
            updated = new_key
        else:
            self.env_pairs[key] = raw
            self.env_sets[self.selected_env_name] = self.env_pairs
            updated = key
        self.mode = MODE_ENV_SELECT
        self.message = f"Updated {field_label.lower()}."
        self.notify_env_mutated()
        return updated

    def delete_env_key(self, key: str) -> bool:
        self.ensure_env_workspace()
        if key not in self.env_pairs:
            return False
        del self.env_pairs[key]
        self.env_sets[self.selected_env_name] = self.env_pairs
        self.clamp_selected_env_index()
        self.mode = MODE_NORMAL
        self.selected_env_field_index = 0
        self.message = f"Deleted {key}."
        self.notify_env_mutated()
        return True

    def delete_selected_env_item(self) -> str | None:
        item = self.get_selected_env_item()
        if item is None:
            return None
        key, _ = item
        deleted = self.delete_env_key(key)
        if not deleted:
            return None
        if self.env_pairs:
            self.mode = MODE_NORMAL
            self.message = "Deleted row."
        return key
