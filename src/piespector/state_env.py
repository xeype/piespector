from __future__ import annotations

from piespector.domain.editor import TAB_ENV
from piespector.domain.modes import MODE_ENV_EDIT, MODE_ENV_SELECT, MODE_NORMAL
from piespector.domain.requests import EnvVariable

ENV_FIELD_COUNT = 4
ENV_FIELDS = [
    ("key", "Variable"),
    ("value", "Value"),
    ("description", "Description"),
    ("sensitive", "Sensitive"),
]


class EnvStateMixin:
    def ensure_env_workspace(self) -> None:
        if not self.env_names:
            self.env_names = ["Default"]
        if not self.env_sets:
            self.env_sets = {"Default": []}
        for name in list(self.env_names):
            self.env_sets.setdefault(name, [])
        self.env_names = [name for name in self.env_names if name in self.env_sets]
        if not self.env_names:
            self.env_names = ["Default"]
            self.env_sets = {"Default": []}
        if self.selected_env_name not in self.env_sets:
            self.selected_env_name = self.env_names[0]
        self._refresh_env_pairs()

    def _refresh_env_pairs(self) -> None:
        items = self.env_sets.get(self.selected_env_name, [])
        self.env_pairs = {v.key: v.value for v in items if v.key}

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
        self._refresh_env_pairs()
        self.selected_env_index = 0
        self.env_scroll_offset = 0
        self.selected_env_field_index = 0
        self.env_creating_new = False
        self.message = f"Selected env {self.selected_env_name}."
        self.notify_env_mutated()

    def select_env_by_name(self, name: str) -> None:
        self.ensure_env_workspace()
        if name in self.env_sets:
            self.selected_env_name = name
            self._refresh_env_pairs()
            self.selected_env_index = 0
            self.env_scroll_offset = 0
            self.selected_env_field_index = 0
            self.env_creating_new = False

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
        self.env_sets[env_name] = []
        self.selected_env_name = env_name
        self._refresh_env_pairs()
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
        variables = self.env_sets.pop(old_name, [])
        self.env_sets[new_name] = variables
        self.env_names = [new_name if item == old_name else item for item in self.env_names]
        self.selected_env_name = new_name
        self._refresh_env_pairs()
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
        self._refresh_env_pairs()
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
            self.env_sets[unique_name] = [
                EnvVariable(key=k, value=v) for k, v in pairs.items() if k
            ]
            imported_names.append(unique_name)

        if not imported_names:
            self.message = "No envs found in import file."
            return 0

        self.selected_env_name = imported_names[0]
        self._refresh_env_pairs()
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

    def get_env_items(self) -> list[EnvVariable]:
        self.ensure_env_workspace()
        return list(self.env_sets.get(self.selected_env_name, []))

    def clamp_selected_env_index(self) -> None:
        items = self.get_env_items()
        if not items:
            self.selected_env_index = 0
            return
        # Allow index == len(items) for the "Add variable" row
        self.selected_env_index = max(0, min(self.selected_env_index, len(items)))

    def clamp_env_scroll_offset(self, visible_rows: int) -> None:
        item_count = len(self.get_env_items())
        max_offset = max(item_count - max(visible_rows, 1), 0)
        self.env_scroll_offset = max(0, min(self.env_scroll_offset, max_offset))

    def select_env_row(self, step: int) -> None:
        items = self.get_env_items()
        # +1 to include the "Add variable" row
        row_count = len(items) + 1
        self.selected_env_index = (self.selected_env_index + step) % row_count

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
        self.selected_env_field_index = (self.selected_env_field_index + step) % ENV_FIELD_COUNT

    def selected_env_field(self) -> tuple[str, str]:
        return ENV_FIELDS[self.selected_env_field_index % ENV_FIELD_COUNT]

    def enter_env_edit_mode(self) -> None:
        items = self.get_env_items()
        if self.selected_env_index >= len(items):
            self.enter_env_create_mode()
            return
        item = self.get_selected_env_item()
        if item is None:
            self.message = "Nothing to edit."
            self.mode = MODE_NORMAL
            return
        field_name, _ = self.selected_env_field()
        if field_name == "sensitive":
            # Toggle directly without opening text input
            self.toggle_selected_env_sensitive()
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

    def get_selected_env_item(self) -> EnvVariable | None:
        items = self.get_env_items()
        if not items:
            return None
        self.clamp_selected_env_index()
        if self.selected_env_index >= len(items):
            return None
        return items[self.selected_env_index]

    def toggle_selected_env_sensitive(self) -> None:
        items = self.env_sets.get(self.selected_env_name, [])
        if not items:
            return
        self.clamp_selected_env_index()
        if self.selected_env_index >= len(items):
            return
        item = items[self.selected_env_index]
        item.sensitive = not item.sensitive
        self._refresh_env_pairs()
        self.mode = MODE_ENV_SELECT
        self.message = f"Sensitive {'on' if item.sensitive else 'off'}."
        self.notify_env_mutated()

    def save_selected_env_field(self, value: str | None = None) -> str | None:
        self.ensure_env_workspace()
        field_name, field_label = self.selected_env_field()
        raw = value or ""

        if self.env_creating_new:
            if field_name != "key":
                return None
            new_key = raw.strip()
            if not new_key:
                self.message = "Variable cannot be empty."
                return None
            items = self.env_sets.get(self.selected_env_name, [])
            if any(v.key == new_key for v in items):
                self.message = f"Variable {new_key!r} already exists."
                return None
            items.append(EnvVariable(key=new_key))
            self.env_sets[self.selected_env_name] = items
            self.selected_env_index = len(items) - 1
            self.selected_env_field_index = 1  # advance to value field
            self.env_creating_new = False
            self.mode = MODE_ENV_EDIT
            self._refresh_env_pairs()
            self.message = ""
            self.notify_env_mutated()
            return new_key

        items = self.env_sets.get(self.selected_env_name, [])
        if not items:
            return None
        self.clamp_selected_env_index()
        if self.selected_env_index >= len(items):
            return None
        item = items[self.selected_env_index]

        if field_name == "key":
            new_key = raw.strip()
            if not new_key:
                self.message = "Variable cannot be empty."
                return None
            if new_key != item.key and any(v.key == new_key for v in items):
                self.message = f"Variable {new_key!r} already exists."
                return None
            item.key = new_key
        elif field_name == "value":
            item.value = raw
        elif field_name == "description":
            item.description = raw
        # sensitive is toggled via toggle_selected_env_sensitive

        self._refresh_env_pairs()
        self.mode = MODE_ENV_SELECT
        self.message = f"Updated {field_label.lower()}."
        self.notify_env_mutated()
        return item.key

    def upsert_env_variable(self, key: str, value: str) -> None:
        """Add or update an env variable (used by the set command)."""
        self.ensure_env_workspace()
        items = self.env_sets.get(self.selected_env_name, [])
        for item in items:
            if item.key == key:
                item.value = value
                self._refresh_env_pairs()
                self.notify_env_mutated()
                return
        items.append(EnvVariable(key=key, value=value))
        self.env_sets[self.selected_env_name] = items
        self._refresh_env_pairs()
        self.notify_env_mutated()

    def delete_env_key(self, key: str) -> bool:
        self.ensure_env_workspace()
        items = self.env_sets.get(self.selected_env_name, [])
        new_items = [v for v in items if v.key != key]
        if len(new_items) == len(items):
            return False
        self.env_sets[self.selected_env_name] = new_items
        self._refresh_env_pairs()
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
        key = item.key
        deleted = self.delete_env_key(key)
        if not deleted:
            return None
        self.mode = MODE_ENV_SELECT
        self.message = "Deleted row."
        return key
