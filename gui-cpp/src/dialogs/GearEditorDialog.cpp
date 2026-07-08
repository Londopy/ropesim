// gui-cpp/src/dialogs/GearEditorDialog.cpp

#include "dialogs/GearEditorDialog.h"

#include <QComboBox>
#include <QDialogButtonBox>
#include <QDoubleSpinBox>
#include <QFormLayout>
#include <QHBoxLayout>

GearEditorDialog::GearEditorDialog(QWidget* parent) : QDialog(parent) {
    setWindowTitle(tr("Gear Editor"));
    auto* form = new QFormLayout(this);

    m_type = new QComboBox(this);
    m_type->addItems({tr("Bolt"), tr("Cam"), tr("Nut")});
    form->addRow(tr("Type"), m_type);

    m_mbs = new QDoubleSpinBox(this);
    m_mbs->setRange(2.0, 50.0);
    m_mbs->setValue(25.0);
    m_mbs->setSuffix(" kN");
    form->addRow(tr("MBS"), m_mbs);

    m_quality = new QDoubleSpinBox(this);
    m_quality->setRange(0.1, 1.0);
    m_quality->setSingleStep(0.05);
    m_quality->setValue(1.0);
    m_quality->setToolTip(tr("Placement quality: 1.0 = textbook, 0.5 = marginal"));
    form->addRow(tr("Quality"), m_quality);

    auto* dirRow = new QHBoxLayout;
    for (auto** sb : {&m_dirX, &m_dirY, &m_dirZ}) {
        *sb = new QDoubleSpinBox(this);
        (*sb)->setRange(-1.0, 1.0);
        (*sb)->setSingleStep(0.1);
        dirRow->addWidget(*sb);
    }
    m_dirY->setValue(-1.0);
    form->addRow(tr("Pull direction"), dirRow);

    auto* buttons = new QDialogButtonBox(
        QDialogButtonBox::Ok | QDialogButtonBox::Cancel, this);
    connect(buttons, &QDialogButtonBox::accepted, this, &QDialog::accept);
    connect(buttons, &QDialogButtonBox::rejected, this, &QDialog::reject);
    form->addRow(buttons);
}

void GearEditorDialog::load(const GearEditResult& g) {
    m_type->setCurrentIndex(g.gearType - 1);
    m_mbs->setValue(g.mbsKn);
    m_quality->setValue(g.quality);
    m_dirX->setValue(g.pullDir.x);
    m_dirY->setValue(g.pullDir.y);
    m_dirZ->setValue(g.pullDir.z);
}

GearEditResult GearEditorDialog::result() const {
    GearEditResult g;
    g.gearType = m_type->currentIndex() + 1;
    g.mbsKn = m_mbs->value();
    g.quality = m_quality->value();
    g.pullDir = {static_cast<float>(m_dirX->value()),
                 static_cast<float>(m_dirY->value()),
                 static_cast<float>(m_dirZ->value())};
    return g;
}
