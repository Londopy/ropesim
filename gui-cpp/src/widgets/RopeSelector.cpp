// gui-cpp/src/widgets/RopeSelector.cpp

#include "widgets/RopeSelector.h"

#include <QComboBox>
#include <QCompleter>
#include <QLabel>
#include <QVBoxLayout>

RopeSelector::RopeSelector(RopeDatabase* db, QWidget* parent)
    : QWidget(parent), m_db(db) {
    auto* layout = new QVBoxLayout(this);
    layout->setContentsMargins(0, 0, 0, 0);

    m_combo = new QComboBox(this);
    m_combo->setEditable(true);
    m_combo->setInsertPolicy(QComboBox::NoInsert);
    layout->addWidget(m_combo);

    m_summary = new QLabel(this);
    m_summary->setWordWrap(true);
    m_summary->setStyleSheet("color: #6b7d6c; font-size: 11px;");
    layout->addWidget(m_summary);

    refresh();
    connect(m_combo, &QComboBox::currentIndexChanged, this,
            &RopeSelector::onIndexChanged);
}

void RopeSelector::refresh() {
    const QString current = m_combo->currentText();
    m_combo->blockSignals(true);
    m_combo->clear();
    m_combo->addItems(m_db->ropeNames());
    m_combo->setCompleter(new QCompleter(m_db->ropeNames(), m_combo));
    m_combo->completer()->setCaseSensitivity(Qt::CaseInsensitive);
    m_combo->completer()->setFilterMode(Qt::MatchContains);
    if (!current.isEmpty()) m_combo->setCurrentText(current);
    m_combo->blockSignals(false);
    onIndexChanged(m_combo->currentIndex());
}

void RopeSelector::selectRope(const QString& name) {
    m_combo->setCurrentText(name);
}

std::optional<RopeSpec> RopeSelector::currentRope() const {
    return m_db->findByName(m_combo->currentText());
}

void RopeSelector::onIndexChanged(int) {
    const auto rope = currentRope();
    if (!rope) {
        m_summary->clear();
        return;
    }
    m_summary->setText(QStringLiteral("⌀ %1 mm · %2 g/m · IF %3 kN · %4 falls · %5")
                           .arg(rope->diameterMm)
                           .arg(rope->weightGPerM)
                           .arg(rope->impactForceKn)
                           .arg(rope->numberOfFalls)
                           .arg(rope->dryTreated ? "dry" : "non-dry"));
    emit ropeChanged(*rope);
}
