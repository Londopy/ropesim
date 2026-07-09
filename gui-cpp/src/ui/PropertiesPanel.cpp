// gui-cpp/src/ui/PropertiesPanel.cpp

#include "ui/PropertiesPanel.h"

#include <QButtonGroup>
#include <QCheckBox>
#include <QComboBox>
#include <QDoubleSpinBox>
#include <QFormLayout>
#include <QGroupBox>
#include <QHBoxLayout>
#include <QLabel>
#include <QPushButton>
#include <QRadioButton>
#include <QScrollArea>
#include <QSlider>
#include <QSpinBox>
#include <QVBoxLayout>

#include "widgets/RopeSelector.h"

namespace {
// Belay device order matches RopesimBelayDevice discriminants.
const char* kDevices[] = {"ATC",       "GriGri",   "Tube",     "Reverso",
                          "Reverso (guide)", "Mega Jul", "Giga Jul", "Click Up",
                          "I-Device",  "Sum",      "Munter"};
} // namespace

PropertiesPanel::PropertiesPanel(RopeDatabase* db, QWidget* parent)
    : QWidget(parent), m_db(db) {
    auto* outer = new QVBoxLayout(this);
    outer->setContentsMargins(0, 0, 0, 0);

    auto* scroll = new QScrollArea(this);
    scroll->setWidgetResizable(true);
    scroll->setFrameShape(QFrame::NoFrame);
    outer->addWidget(scroll);

    auto* content = new QWidget;
    auto* layout = new QVBoxLayout(content);
    layout->addWidget(buildRopeSection());
    layout->addWidget(buildClimberSection());
    layout->addWidget(buildEnvironmentSection());
    layout->addWidget(buildPhysicsSection());
    layout->addWidget(buildScenarioSection());
    layout->addStretch(1);
    scroll->setWidget(content);

    setMinimumWidth(260);
}

QWidget* PropertiesPanel::buildRopeSection() {
    auto* box = new QGroupBox(tr("Rope"), this);
    auto* layout = new QVBoxLayout(box);

    m_ropeSelector = new RopeSelector(m_db, box);
    layout->addWidget(m_ropeSelector);
    connect(m_ropeSelector, &RopeSelector::ropeChanged, this,
            [this](const RopeSpec&) { emit paramsChanged(); });

    auto* buttons = new QHBoxLayout;
    auto* addBtn = new QPushButton(tr("Add New"), box);
    auto* editBtn = new QPushButton(tr("Edit"), box);
    buttons->addWidget(addBtn);
    buttons->addWidget(editBtn);
    layout->addLayout(buttons);
    connect(addBtn, &QPushButton::clicked, this,
            [this] { emit editRopeRequested(true); });
    connect(editBtn, &QPushButton::clicked, this,
            [this] { emit editRopeRequested(false); });

    auto* form = new QFormLayout;
    m_fallsTaken = new QSpinBox(box);
    m_fallsTaken->setRange(0, 99);
    form->addRow(tr("Falls taken"), m_fallsTaken);
    layout->addLayout(form);

    m_retirementLabel = new QLabel(box);
    m_retirementLabel->setWordWrap(true);
    m_retirementLabel->setStyleSheet("color: #e8b84b; font-size: 11px;");
    layout->addWidget(m_retirementLabel);

    connect(m_fallsTaken, &QSpinBox::valueChanged, this, [this](int falls) {
        const auto rope = m_ropeSelector->currentRope();
        if (rope) {
            const int rated = rope->numberOfFalls;
            if (falls >= rated)
                m_retirementLabel->setText(
                    tr("⚠ Exceeded rated falls (%1/%2) — retire this rope.")
                        .arg(falls).arg(rated));
            else if (falls >= rated * 0.8)
                m_retirementLabel->setText(
                    tr("⚠ At %1% of rated falls — inspect carefully.")
                        .arg(100 * falls / rated));
            else
                m_retirementLabel->clear();
        }
        emit paramsChanged();
    });
    return box;
}

QWidget* PropertiesPanel::buildClimberSection() {
    auto* box = new QGroupBox(tr("Climber"), this);
    auto* form = new QFormLayout(box);

    m_mass = new QDoubleSpinBox(box);
    m_mass->setRange(20, 200);
    m_mass->setValue(80);
    m_mass->setSuffix(" kg");
    form->addRow(tr("Mass"), m_mass);

    m_height = new QDoubleSpinBox(box);
    m_height->setRange(1.0, 2.3);
    m_height->setSingleStep(0.05);
    m_height->setValue(1.75);
    m_height->setSuffix(" m");
    form->addRow(tr("Height"), m_height);

    m_device = new QComboBox(box);
    for (const char* d : kDevices) m_device->addItem(d);
    form->addRow(tr("Belay device"), m_device);

    m_belayerMass = new QDoubleSpinBox(box);
    m_belayerMass->setRange(20, 200);
    m_belayerMass->setValue(75);
    m_belayerMass->setSuffix(" kg");
    form->addRow(tr("Belayer mass"), m_belayerMass);

    m_dynamicBelay = new QCheckBox(tr("Dynamic belay"), box);
    m_dynamicBelay->setChecked(true);
    form->addRow(QString(), m_dynamicBelay);

    for (auto* sb : {m_mass, m_height, m_belayerMass})
        connect(sb, &QDoubleSpinBox::valueChanged, this,
                [this](double) { emit paramsChanged(); });
    connect(m_device, &QComboBox::currentIndexChanged, this,
            [this](int) { emit paramsChanged(); });
    connect(m_dynamicBelay, &QCheckBox::toggled, this,
            [this](bool) { emit paramsChanged(); });
    return box;
}

QWidget* PropertiesPanel::buildEnvironmentSection() {
    auto* box = new QGroupBox(tr("Environment"), this);
    auto* form = new QFormLayout(box);

    m_rockType = new QComboBox(box);
    m_rockType->addItems({"granite", "limestone", "sandstone", "basalt", "ice"});
    form->addRow(tr("Rock type"), m_rockType);
    connect(m_rockType, &QComboBox::currentTextChanged, this,
            [this](const QString& t) {
                emit rockTypeChanged(t);
                emit paramsChanged();
            });

    auto* wetRow = new QHBoxLayout;
    auto* dry = new QRadioButton(tr("Dry"), box);
    auto* wet = new QRadioButton(tr("Wet"), box);
    dry->setChecked(true);
    m_wetGroup = new QButtonGroup(box);
    m_wetGroup->addButton(dry, 0);
    m_wetGroup->addButton(wet, 1);
    wetRow->addWidget(dry);
    wetRow->addWidget(wet);
    form->addRow(tr("Conditions"), wetRow);
    connect(m_wetGroup, &QButtonGroup::idClicked, this,
            [this](int) { emit paramsChanged(); });

    m_temperature = new QSlider(Qt::Horizontal, box);
    m_temperature->setRange(-20, 40);
    m_temperature->setValue(15);
    m_tempLabel = new QLabel(tr("15 °C / 59 °F"), box);
    auto* tRow = new QVBoxLayout;
    tRow->addWidget(m_temperature);
    tRow->addWidget(m_tempLabel);
    form->addRow(tr("Temperature"), tRow);
    connect(m_temperature, &QSlider::valueChanged, this, [this](int c) {
        m_tempLabel->setText(
            tr("%1 °C / %2 °F").arg(c).arg(c * 9 / 5 + 32));
        emit paramsChanged();
    });

    m_routeAngle = new QSlider(Qt::Horizontal, box);
    m_routeAngle->setRange(0, 130);
    m_routeAngle->setValue(90);
    m_angleLabel = new QLabel(tr("90° (vertical)"), box);
    auto* aRow = new QVBoxLayout;
    aRow->addWidget(m_routeAngle);
    aRow->addWidget(m_angleLabel);
    form->addRow(tr("Route angle"), aRow);
    connect(m_routeAngle, &QSlider::valueChanged, this, [this](int a) {
        m_angleLabel->setText(a < 88    ? tr("%1° (slab)").arg(a)
                              : a <= 92 ? tr("%1° (vertical)").arg(a)
                                        : tr("%1° (overhang)").arg(a));
        emit routeAngleChanged(a);
        emit paramsChanged();
    });
    return box;
}

QWidget* PropertiesPanel::buildPhysicsSection() {
    auto* box = new QGroupBox(tr("Physics"), this);
    auto* form = new QFormLayout(box);

    auto* modeRow = new QHBoxLayout;
    auto* analytical = new QRadioButton(tr("Analytical"), box);
    auto* rapier = new QRadioButton(tr("Rapier 3D"), box);
    analytical->setChecked(true);
    m_physicsGroup = new QButtonGroup(box);
    m_physicsGroup->addButton(analytical, 0);
    m_physicsGroup->addButton(rapier, 1);
    modeRow->addWidget(analytical);
    modeRow->addWidget(rapier);
    form->addRow(tr("Mode"), modeRow);
    connect(m_physicsGroup, &QButtonGroup::idClicked, this,
            [this](int) { emit paramsChanged(); });

    m_linkSpacing = new QComboBox(box);
    m_linkSpacing->addItem(tr("Fine (0.10 m)"), 0.10);
    m_linkSpacing->addItem(tr("Medium (0.25 m)"), 0.25);
    m_linkSpacing->addItem(tr("Coarse (0.50 m)"), 0.50);
    m_linkSpacing->setCurrentIndex(1);
    form->addRow(tr("Link spacing"), m_linkSpacing);

    m_timestep = new QComboBox(box);
    m_timestep->addItem("1/480 s", 1.0 / 480.0);
    m_timestep->addItem("1/240 s", 1.0 / 240.0);
    m_timestep->addItem("1/120 s", 1.0 / 120.0);
    m_timestep->setCurrentIndex(1);
    form->addRow(tr("Timestep"), m_timestep);

    m_rockPreset = new QComboBox(box);
    m_rockPreset->addItems({tr("Vertical slab"), tr("Overhang 30°"),
                            tr("Overhang 45°"), tr("Roof"), tr("Crack system"),
                            tr("Corner"), tr("Arête")});
    form->addRow(tr("Rock face"), m_rockPreset);
    connect(m_rockPreset, &QComboBox::currentIndexChanged, this,
            [this](int i) { emit rockPresetChanged(i); });

    return box;
}

QWidget* PropertiesPanel::buildScenarioSection() {
    auto* box = new QGroupBox(tr("Scenario"), this);
    auto* layout = new QVBoxLayout(box);
    auto* form = new QFormLayout;
    layout->addLayout(form);

    m_scenarioType = new QComboBox(box);
    m_scenarioType->addItems({"Lead", "Top-Rope", "Rappel", "Haul", "Lower"});
    form->addRow(tr("Type"), m_scenarioType);

    m_climberRouteHeight = new QDoubleSpinBox(box);
    m_climberRouteHeight->setRange(0.5, 60);
    m_climberRouteHeight->setValue(12);
    m_climberRouteHeight->setSuffix(" m");
    form->addRow(tr("Climber height"), m_climberRouteHeight);

    m_lastPieceHeight = new QDoubleSpinBox(box);
    m_lastPieceHeight->setRange(0.0, 60);
    m_lastPieceHeight->setValue(10);
    m_lastPieceHeight->setSuffix(" m");
    form->addRow(tr("Last piece height"), m_lastPieceHeight);

    // Context-sensitive rows
    auto makeRow = [&layout, box](const QString& label, QWidget* field) {
        auto* row = new QWidget(box);
        auto* h = new QHBoxLayout(row);
        h->setContentsMargins(0, 0, 0, 0);
        h->addWidget(new QLabel(label, row));
        h->addWidget(field, 1);
        layout->addWidget(row);
        return row;
    };

    m_slack = new QDoubleSpinBox(box);
    m_slack->setRange(0, 10);
    m_slack->setValue(1.0);
    m_slack->setSuffix(" m");
    m_topRopeRow = makeRow(tr("Slack"), m_slack);

    auto* rappelBox = new QWidget(box);
    auto* rl = new QHBoxLayout(rappelBox);
    rl->setContentsMargins(0, 0, 0, 0);
    m_rappelSpeed = new QDoubleSpinBox(rappelBox);
    m_rappelSpeed->setRange(0.1, 8);
    m_rappelSpeed->setValue(2.0);
    m_rappelSpeed->setSuffix(" m/s");
    m_suddenStop = new QCheckBox(tr("Sudden stop"), rappelBox);
    rl->addWidget(m_rappelSpeed);
    rl->addWidget(m_suddenStop);
    m_rappelRow = makeRow(tr("Rappel"), rappelBox);

    auto* haulBox = new QWidget(box);
    auto* hl = new QHBoxLayout(haulBox);
    hl->setContentsMargins(0, 0, 0, 0);
    m_haulSystem = new QComboBox(haulBox);
    m_haulSystem->addItems({"3:1", "5:1", "6:1", "piggyback"});
    m_haulLoad = new QDoubleSpinBox(haulBox);
    m_haulLoad->setRange(10, 300);
    m_haulLoad->setValue(80);
    m_haulLoad->setSuffix(" kg");
    hl->addWidget(m_haulSystem);
    hl->addWidget(m_haulLoad);
    m_haulRow = makeRow(tr("Haul"), haulBox);

    auto syncRows = [this](const QString& type) {
        m_topRopeRow->setVisible(type == "Top-Rope");
        m_rappelRow->setVisible(type == "Rappel");
        m_haulRow->setVisible(type == "Haul");
        emit paramsChanged();
    };
    connect(m_scenarioType, &QComboBox::currentTextChanged, this, syncRows);
    syncRows("Lead");

    for (auto* sb : {m_climberRouteHeight, m_lastPieceHeight, m_slack,
                     m_rappelSpeed, m_haulLoad})
        connect(sb, &QDoubleSpinBox::valueChanged, this,
                [this](double) { emit paramsChanged(); });
    return box;
}

ScenarioParams PropertiesPanel::params() const {
    ScenarioParams p;
    if (const auto rope = m_ropeSelector->currentRope()) p.rope = *rope;
    p.fallsTaken = m_fallsTaken->value();

    p.climberMassKg = m_mass->value();
    p.climberHeightM = m_height->value();
    p.belayDevice = m_device->currentIndex();
    p.belayerMassKg = m_belayerMass->value();
    p.dynamicBelay = m_dynamicBelay->isChecked();

    p.rockType = m_rockType->currentText();
    p.wet = m_wetGroup->checkedId() == 1;
    p.temperatureC = m_temperature->value();
    p.routeAngleDeg = m_routeAngle->value();

    p.useRapier = m_physicsGroup->checkedId() == 1;
    p.linkSpacingM = m_linkSpacing->currentData().toDouble();
    p.timestepS = m_timestep->currentData().toDouble();
    p.rockPreset = m_rockPreset->currentIndex();

    p.scenarioType = m_scenarioType->currentText();
    p.topRopeSlackM = m_slack->value();
    p.rappelSpeedMps = m_rappelSpeed->value();
    p.rappelSuddenStop = m_suddenStop->isChecked();
    p.haulSystem = m_haulSystem->currentIndex();
    p.haulLoadKg = m_haulLoad->value();
    p.climberRouteHeightM = m_climberRouteHeight->value();
    p.lastPieceHeightM = m_lastPieceHeight->value();
    return p;
}

void PropertiesPanel::refreshRopes() { m_ropeSelector->refresh(); }

void PropertiesPanel::applyDemoPreset() {
    // A realistic factor-~0.27 lead fall on a skinny single rope. Setting the
    // widgets (rather than a detached params struct) means the whole left
    // panel visibly reflects the demo, and the normal run path picks it up.
    m_ropeSelector->selectRope(QStringLiteral("Beal Opera 8.5 Dry"));
    m_scenarioType->setCurrentText(QStringLiteral("Lead"));
    m_mass->setValue(80.0);
    m_climberRouteHeight->setValue(17.0);
    m_lastPieceHeight->setValue(15.0);
    m_routeAngle->setValue(90);        // vertical wall (QSlider, integer degrees)
    m_temperature->setValue(15);       // °C
    m_dynamicBelay->setChecked(true);
    m_linkSpacing->setCurrentIndex(1); // medium
    m_timestep->setCurrentIndex(1);    // 1/240 s
    emit paramsChanged();
}
