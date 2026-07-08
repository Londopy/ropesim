// gui-cpp/src/dialogs/RopeEditorDialog.cpp

#include "dialogs/RopeEditorDialog.h"

#include <QCheckBox>
#include <QComboBox>
#include <QDialogButtonBox>
#include <QDoubleSpinBox>
#include <QFormLayout>
#include <QGroupBox>
#include <QLabel>
#include <QLineEdit>
#include <QSpinBox>
#include <QVBoxLayout>

RopeEditorDialog::RopeEditorDialog(RopeDatabase* db, QWidget* parent)
    : QDialog(parent), m_db(db) {
    setWindowTitle(tr("Rope Editor"));
    auto* layout = new QVBoxLayout(this);
    auto* form = new QFormLayout;
    layout->addLayout(form);

    m_name = new QLineEdit(this);
    form->addRow(tr("Name"), m_name);
    m_manufacturer = new QLineEdit(this);
    form->addRow(tr("Manufacturer"), m_manufacturer);

    m_type = new QComboBox(this);
    m_type->addItems({"single", "dry_single", "half", "twin"});
    form->addRow(tr("Type"), m_type);

    m_diameter = new QDoubleSpinBox(this);
    m_diameter->setRange(6.0, 12.0);
    m_diameter->setSingleStep(0.1);
    m_diameter->setValue(9.8);
    m_diameter->setSuffix(" mm");
    form->addRow(tr("Diameter"), m_diameter);

    m_weight = new QDoubleSpinBox(this);
    m_weight->setRange(30, 110);
    m_weight->setValue(62);
    m_weight->setSuffix(" g/m");
    form->addRow(tr("Weight"), m_weight);

    m_impactForce = new QDoubleSpinBox(this);
    m_impactForce->setRange(4.0, 14.0);
    m_impactForce->setSingleStep(0.1);
    m_impactForce->setValue(8.5);
    m_impactForce->setSuffix(" kN");
    form->addRow(tr("Impact force"), m_impactForce);

    m_falls = new QSpinBox(this);
    m_falls->setRange(1, 30);
    m_falls->setValue(7);
    form->addRow(tr("UIAA falls"), m_falls);

    m_staticElong = new QDoubleSpinBox(this);
    m_staticElong->setRange(1.0, 15.0);
    m_staticElong->setValue(8.0);
    m_staticElong->setSuffix(" %");
    form->addRow(tr("Static elongation"), m_staticElong);

    m_dynamicElong = new QDoubleSpinBox(this);
    m_dynamicElong->setRange(10.0, 45.0);
    m_dynamicElong->setValue(33.0);
    m_dynamicElong->setSuffix(" %");
    form->addRow(tr("Dynamic elongation"), m_dynamicElong);

    m_sheath = new QDoubleSpinBox(this);
    m_sheath->setRange(20, 55);
    m_sheath->setValue(38);
    m_sheath->setSuffix(" %");
    form->addRow(tr("Sheath"), m_sheath);

    m_length = new QDoubleSpinBox(this);
    m_length->setRange(10, 100);
    m_length->setValue(60);
    m_length->setSuffix(" m");
    form->addRow(tr("Length"), m_length);

    m_dry = new QCheckBox(tr("Dry treated"), this);
    form->addRow(QString(), m_dry);

    // ── Live compliance preview ─────────────────────────────────────────
    auto* box = new QGroupBox(tr("EN 892 / UIAA 101 compliance"), this);
    auto* cLayout = new QVBoxLayout(box);
    m_cImpact = new QLabel(box);
    m_cStatic = new QLabel(box);
    m_cDynamic = new QLabel(box);
    m_cFalls = new QLabel(box);
    for (auto* l : {m_cImpact, m_cStatic, m_cDynamic, m_cFalls})
        cLayout->addWidget(l);
    layout->addWidget(box);

    m_error = new QLabel(this);
    m_error->setStyleSheet("color: #e05050;");
    m_error->setWordWrap(true);
    layout->addWidget(m_error);

    auto* buttons = new QDialogButtonBox(
        QDialogButtonBox::Save | QDialogButtonBox::Cancel, this);
    connect(buttons, &QDialogButtonBox::accepted, this, &QDialog::accept);
    connect(buttons, &QDialogButtonBox::rejected, this, &QDialog::reject);
    layout->addWidget(buttons);

    for (auto* sb : {m_diameter, m_weight, m_impactForce, m_staticElong,
                     m_dynamicElong, m_sheath, m_length})
        connect(sb, &QDoubleSpinBox::valueChanged, this,
                [this](double) { updateCompliance(); });
    connect(m_falls, &QSpinBox::valueChanged, this,
            [this](int) { updateCompliance(); });
    connect(m_type, &QComboBox::currentIndexChanged, this,
            [this](int) { updateCompliance(); });
    updateCompliance();
}

void RopeEditorDialog::updateCompliance() {
    const bool single = m_type->currentText().contains("single");
    const double maxImpact = single ? 12.0 : 8.0; // half-rope limit
    auto mark = [](QLabel* l, bool pass, const QString& text) {
        l->setText((pass ? "✔ " : "✘ ") + text);
        l->setStyleSheet(pass ? "color: #7ecf45;" : "color: #e05050;");
    };
    mark(m_cImpact, m_impactForce->value() <= maxImpact,
         tr("Impact force ≤ %1 kN").arg(maxImpact));
    mark(m_cStatic, m_staticElong->value() <= (single ? 10.0 : 12.0),
         tr("Static elongation ≤ %1 %").arg(single ? 10 : 12));
    mark(m_cDynamic, m_dynamicElong->value() <= 40.0,
         tr("Dynamic elongation ≤ 40 %"));
    mark(m_cFalls, m_falls->value() >= 5, tr("≥ 5 UIAA test falls"));
}

void RopeEditorDialog::loadSpec(const RopeSpec& s) {
    m_name->setText(s.name);
    m_manufacturer->setText(s.manufacturer);
    m_type->setCurrentText(s.ropeType);
    m_diameter->setValue(s.diameterMm);
    m_weight->setValue(s.weightGPerM);
    m_impactForce->setValue(s.impactForceKn);
    m_falls->setValue(s.numberOfFalls);
    m_staticElong->setValue(s.staticElongationPct);
    m_dynamicElong->setValue(s.dynamicElongationPct);
    m_sheath->setValue(s.sheathPercentage);
    m_length->setValue(s.lengthM);
    m_dry->setChecked(s.dryTreated);
    updateCompliance();
}

RopeSpec RopeEditorDialog::spec() const {
    RopeSpec s;
    s.name = m_name->text().trimmed();
    s.manufacturer = m_manufacturer->text().trimmed();
    s.ropeType = m_type->currentText();
    s.diameterMm = m_diameter->value();
    s.weightGPerM = m_weight->value();
    s.impactForceKn = m_impactForce->value();
    s.numberOfFalls = m_falls->value();
    s.staticElongationPct = m_staticElong->value();
    s.dynamicElongationPct = m_dynamicElong->value();
    s.sheathPercentage = m_sheath->value();
    s.lengthM = m_length->value();
    s.dryTreated = m_dry->isChecked();
    return s;
}

void RopeEditorDialog::accept() {
    m_error->clear();
    const RopeSpec s = spec();
    QStringList problems;
    if (s.name.isEmpty()) problems << tr("name is required");
    if (s.manufacturer.isEmpty()) problems << tr("manufacturer is required");
    if (s.dynamicElongationPct <= s.staticElongationPct)
        problems << tr("dynamic elongation must exceed static elongation");
    if (!problems.isEmpty()) {
        m_error->setText(problems.join("; "));
        return;
    }
    m_db->upsert(s);
    if (!m_db->save()) {
        m_error->setText(tr("could not write %1").arg(m_db->path()));
        return;
    }
    QDialog::accept();
}
