"""Help and tooltip UI helpers for StudioApp."""

from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtGui import QEnterEvent, QFont, QHelpEvent
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QToolButton,
    QToolTip,
    QVBoxLayout,
    QWidget,
)

from .i18n import DEFAULT_LOCALE, translate
from .ui_help import HelpEntry, build_help_entry, filter_help_entries


def build_help_tooltip_text(summary: str, *, locale: str = DEFAULT_LOCALE) -> str:
    """Return tooltip text for inline help near the cursor."""
    text = str(summary or "").strip()
    if text:
        return text
    return translate("app.help.tooltip.fallback", locale=locale)


def open_help_guide(self) -> None:
    if self._help_dialog is not None:
        self._help_dialog.raise_()
        self._help_dialog.activateWindow()
        return

    dialog = QDialog(self)
    dialog.setWindowTitle(self._t("app.help.dialog.title"))
    dialog.resize(980, 640)
    self._help_dialog = dialog

    layout = QVBoxLayout(dialog)

    top_layout = QHBoxLayout()
    top_layout.addWidget(QLabel(self._t("app.log.search")))
    search_edit = QLineEdit()
    search_edit.setMinimumWidth(340)
    top_layout.addWidget(search_edit)
    summary_label = QLabel(self._t("app.help.dialog.summary", count=len(self._help_entries_by_id)))
    top_layout.addWidget(summary_label)
    top_layout.addStretch()
    layout.addLayout(top_layout)

    splitter = QSplitter(Qt.Orientation.Horizontal)
    listbox = QListWidget()
    listbox.setFont(QFont("Segoe UI", 10))
    splitter.addWidget(listbox)

    detail_text = QPlainTextEdit()
    detail_text.setReadOnly(True)
    detail_text.setFont(QFont("Consolas", 9))
    splitter.addWidget(detail_text)

    splitter.setStretchFactor(0, 2)
    splitter.setStretchFactor(1, 3)
    layout.addWidget(splitter, 1)

    footer_layout = QHBoxLayout()
    footer_layout.addStretch()
    close_button = QPushButton(self._t("app.button.close"))
    close_button.clicked.connect(self._close_help_dialog)
    footer_layout.addWidget(close_button)
    layout.addLayout(footer_layout)

    visible_entries: list[HelpEntry] = []

    def _render_details(entry: HelpEntry) -> None:
        detail_text.setPlainText(
            self._t(
                "app.help.dialog.details",
                title=entry.title,
                widget_class=entry.widget_class,
                widget_id=entry.widget_id,
                summary=entry.summary,
                detail=entry.detail,
            )
        )

    def _refresh_list() -> None:
        visible_entries.clear()
        listbox.clear()
        filtered = filter_help_entries(self._sorted_help_entries(), search_edit.text())
        for entry in filtered:
            visible_entries.append(entry)
            listbox.addItem(
                self._t(
                    "app.list.item.help_entry",
                    title=entry.title,
                    widget_class=entry.widget_class,
                )
            )
        summary_label.setText(
            self._t(
                "app.help.dialog.shown",
                shown=len(filtered),
                total=len(self._help_entries_by_id),
            )
        )
        if visible_entries:
            listbox.setCurrentRow(0)
            _render_details(visible_entries[0])
        else:
            detail_text.setPlainText(self._t("app.help.dialog.no_match"))

    def _on_select(row: int) -> None:
        if row < 0 or row >= len(visible_entries):
            return
        _render_details(visible_entries[row])

    search_edit.textChanged.connect(lambda: _refresh_list())
    listbox.currentRowChanged.connect(_on_select)

    dialog.finished.connect(lambda: setattr(self, "_help_dialog", None))

    _refresh_list()
    search_edit.setFocus()

    dialog.exec()


def _close_help_dialog(self) -> None:
    if self._help_dialog is None:
        return
    self._help_dialog.close()
    self._help_dialog = None


def _widget_text(self, widget: QWidget) -> str:
    if isinstance(widget, QPushButton):
        text = widget.text().strip()
        if text and any(char.isalnum() for char in text):
            return text
        tooltip = widget.toolTip().strip()
        if tooltip:
            return tooltip
        return text
    if isinstance(widget, QToolButton):
        text = widget.text().strip()
        if text:
            return text
        tooltip = widget.toolTip().strip()
        if tooltip:
            return tooltip
        return widget.objectName()
    if isinstance(widget, QLabel):
        tooltip = widget.toolTip().strip()
        if tooltip:
            return tooltip
        return widget.text()
    if isinstance(widget, QLineEdit):
        placeholder = widget.placeholderText().strip()
        if placeholder:
            return placeholder
        tooltip = widget.toolTip().strip()
        if tooltip:
            return tooltip
        text = widget.text().strip()
        if text:
            return text
        return widget.objectName()
    if isinstance(widget, QComboBox):
        tooltip = widget.toolTip().strip()
        if tooltip:
            return tooltip
        text = widget.currentText().strip()
        if text:
            return text
        return widget.objectName()
    if isinstance(widget, QCheckBox):
        return widget.text()
    if isinstance(widget, QListWidget):
        tooltip = widget.toolTip().strip()
        if tooltip:
            return tooltip
        return widget.objectName()
    if isinstance(widget, QPlainTextEdit):
        tooltip = widget.toolTip().strip()
        if tooltip:
            return tooltip
        return widget.objectName()
    return ""


def _should_skip_help_widget(self, widget: QWidget) -> bool:
    if widget is self:
        return True
    object_name = widget.objectName()
    if object_name.startswith("qt_"):
        return True
    return type(widget).__name__ in {
        "QFrame",
        "QListView",
        "QMenu",
        "QScrollArea",
        "QScrollBar",
        "QSplitter",
        "QSplitterHandle",
        "QStackedWidget",
        "QTabBar",
        "QWidget",
    }


def _register_help_for_widget(self, widget: QWidget) -> None:
    if widget in self._help_entries_by_widget:
        return
    if self._should_skip_help_widget(widget):
        return
    widget_id = widget.objectName() or str(id(widget))
    widget_class = type(widget).__name__
    widget_text = self._widget_text(widget)
    entry = build_help_entry(
        widget_id=widget_id,
        widget_class=widget_class,
        widget_text=widget_text,
        locale=self._translator.locale,
    )
    if entry.summary.strip() == "":
        return
    self._help_entries_by_widget[widget] = entry
    self._help_entries_by_id[entry.widget_id] = entry
    widget.setToolTip(build_help_tooltip_text(entry.summary, locale=self._translator.locale))
    widget.installEventFilter(self)


def _register_help_for_widget_tree(self, root: QWidget) -> None:
    for child in root.findChildren(QWidget):
        self._register_help_for_widget(child)


def eventFilter(self, obj: QObject, event: QEvent) -> bool:
    combo = self._combo_tooltip_viewports.get(obj)
    if combo is not None and event.type() == QEvent.Type.ToolTip:
        if isinstance(event, QHelpEvent):
            index = combo.view().indexAt(event.pos())
            if index.isValid():
                tooltip = index.data(Qt.ItemDataRole.ToolTipRole)
                if tooltip:
                    QToolTip.showText(event.globalPos(), str(tooltip), combo.view())
                    return True
        return False
    if isinstance(obj, QWidget) and event.type() == QEvent.Type.Enter:
        entry = self._help_entries_by_widget.get(obj)
        if entry is None:
            return False
        if isinstance(event, QEnterEvent):
            QToolTip.showText(event.globalPosition().toPoint(), obj.toolTip(), obj)
            return False
        QToolTip.showText(obj.mapToGlobal(obj.rect().center()), obj.toolTip(), obj)
        return False
    if isinstance(obj, QWidget) and event.type() == QEvent.Type.ToolTip:
        entry = self._help_entries_by_widget.get(obj)
        if entry is None:
            return False
        if isinstance(event, QHelpEvent):
            QToolTip.showText(event.globalPos(), obj.toolTip(), obj)
            return True
        return False
    if isinstance(obj, QWidget) and event.type() == QEvent.Type.FocusIn:
        entry = self._help_entries_by_widget.get(obj)
        if entry is not None:
            QToolTip.showText(obj.mapToGlobal(obj.rect().center()), obj.toolTip(), obj)
    if isinstance(obj, QWidget) and event.type() == QEvent.Type.Leave:
        QToolTip.hideText()
    return False


def _sorted_help_entries(self) -> list[HelpEntry]:
    return sorted(
        self._help_entries_by_id.values(),
        key=lambda item: (item.title.lower(), item.widget_class.lower(), item.widget_id),
    )
