# gui/views/library.py
import shutil
from pathlib import Path

from PySide6.QtWidgets import (
    QAbstractItemView, QComboBox, QFileDialog, QHBoxLayout, QHeaderView,
    QLabel, QLineEdit, QPushButton, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QWidget, QMessageBox,
)

_CATEGORIES = {
    "background": ["minecraft_parkour", "subway_surfers", "gta", "satisfying",
                   "nature", "space", "custom"],
    "music": [], "logo": [], "intro": [], "outro": [],
}


class LibraryView(QWidget):
    """Browse / add / remove library media (backgrounds, music, logos, ...)."""

    def __init__(self, container=None, parent=None):
        super().__init__(parent)
        self.container = container
        v = QVBoxLayout(self)
        title = QLabel("Library")
        title.setObjectName("title")
        v.addWidget(title)

        bar = QHBoxLayout()
        self.kind = QComboBox()
        self.kind.addItems(list(_CATEGORIES.keys()))
        self.kind.currentTextChanged.connect(self._on_kind_changed)
        self.category = QComboBox()
        self._populate_categories()
        bar.addWidget(QLabel("Kind")); bar.addWidget(self.kind)
        bar.addWidget(QLabel("Category")); bar.addWidget(self.category)
        add_btn = QPushButton("➕  Add file...")
        add_btn.clicked.connect(self._on_add)
        remove_btn = QPushButton("🗑  Remove")
        remove_btn.clicked.connect(self._on_remove)
        refresh_btn = QPushButton("🔄  Refresh")
        refresh_btn.clicked.connect(self.refresh)
        for b in (add_btn, remove_btn, refresh_btn):
            bar.addWidget(b)
        bar.addStretch()
        v.addLayout(bar)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["ID", "Name", "Path", "Added"])
        self.table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.Stretch)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        v.addWidget(self.table, 1)

    def _populate_categories(self):
        self.category.clear()
        cats = _CATEGORIES.get(self.kind.currentText(), [])
        self.category.addItems(cats if cats else ["(any)"])

    def _on_kind_changed(self):
        self._populate_categories()
        self.refresh()

    def refresh(self) -> None:
        self.table.setRowCount(0)
        if not self.container or not self.container.db:
            return
        from infra.db.repositories import list_media
        kind = self.kind.currentText()
        cat = self.category.currentText()
        rows = list_media(self.container.db, kind=kind,
                          category=cat if cat != "(any)" else "")
        for i, r in enumerate(rows):
            self.table.insertRow(i)
            self.table.setItem(i, 0, QTableWidgetItem(str(r["id"])))
            self.table.setItem(i, 1, QTableWidgetItem(r["name"] or ""))
            self.table.setItem(i, 2, QTableWidgetItem(r["path"] or ""))
            self.table.setItem(i, 3, QTableWidgetItem(r["added_at"] or ""))

    def _on_add(self) -> None:
        if not self.container:
            return
        paths, _ = QFileDialog.getOpenFileNames(self, "Add media", "")
        if not paths:
            return
        from infra.db.repositories import insert_media
        from infra.storage import library_subdir
        kind = self.kind.currentText()
        cat = self.category.currentText()
        cat = cat if cat != "(any)" else ""
        target_dir = library_subdir(self.container.paths, kind + "s", cat)
        for src in paths:
            src_path = Path(src)
            dst = target_dir / src_path.name
            try:
                shutil.copy2(src_path, dst)
            except Exception as e:
                QMessageBox.warning(self, "Add failed", f"{src_path.name}: {e}")
                continue
            insert_media(self.container.db, kind, cat, src_path.stem, str(dst))
        self.refresh()

    def _on_remove(self) -> None:
        rows = {idx.row() for idx in self.table.selectedIndexes()}
        if not rows or not self.container:
            return
        for r in sorted(rows):
            mid = int(self.table.item(r, 0).text())
            path_item = self.table.item(r, 2)
            self.container.db.execute("DELETE FROM media_library WHERE id=?", (mid,))
            self.container.db.commit()
            # Best-effort file removal.
            try:
                if path_item and Path(path_item.text()).exists():
                    Path(path_item.text()).unlink()
            except Exception:
                pass
        self.refresh()
