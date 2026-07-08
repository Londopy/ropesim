// gui-cpp/src/dialogs/PreferencesDialog.cpp

#include "dialogs/PreferencesDialog.h"

#include <QCheckBox>
#include <QComboBox>
#include <QDialogButtonBox>
#include <QFormLayout>
#include <QSettings>

PreferencesDialog::PreferencesDialog(QWidget* parent) : QDialog(parent) {
    setWindowTitle(tr("Preferences"));
    QSettings settings;
    auto* form = new QFormLayout(this);

    m_units = new QComboBox(this);
    m_units->addItems({tr("SI (kN, m, kg)"), tr("Imperial (lbf, ft, lb)")});
    m_units->setCurrentIndex(settings.value("units/imperial", false).toBool() ? 1 : 0);
    form->addRow(tr("Units"), m_units);

    m_gravity = new QComboBox(this);
    m_gravity->addItem(tr("Earth (9.81 m/s²)"), 9.81);
    m_gravity->addItem(tr("Moon (1.62 m/s²) — for fun"), 1.62);
    form->addRow(tr("Gravity"), m_gravity);

    m_autoRun = new QCheckBox(tr("Re-run simulation when parameters change"), this);
    m_autoRun->setChecked(settings.value("sim/autorun", false).toBool());
    form->addRow(QString(), m_autoRun);

    auto* buttons = new QDialogButtonBox(
        QDialogButtonBox::Ok | QDialogButtonBox::Cancel, this);
    connect(buttons, &QDialogButtonBox::accepted, this, [this] {
        save();
        accept();
    });
    connect(buttons, &QDialogButtonBox::rejected, this, &QDialog::reject);
    form->addRow(buttons);
}

void PreferencesDialog::save() {
    QSettings settings;
    settings.setValue("units/imperial", m_units->currentIndex() == 1);
    settings.setValue("sim/gravity", m_gravity->currentData().toDouble());
    settings.setValue("sim/autorun", m_autoRun->isChecked());
}

bool PreferencesDialog::useImperialUnits() {
    return QSettings().value("units/imperial", false).toBool();
}

double PreferencesDialog::defaultGravity() {
    return QSettings().value("sim/gravity", 9.81).toDouble();
}
