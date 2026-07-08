// gui-cpp/src/ui/ResultsPanel.cpp

#include "ui/ResultsPanel.h"

#include <QCheckBox>
#include <QComboBox>
#include <QGridLayout>
#include <QGroupBox>
#include <QHBoxLayout>
#include <QHeaderView>
#include <QLabel>
#include <QPushButton>
#include <QScrollArea>
#include <QTableWidget>
#include <QVBoxLayout>

#include "widgets/ForcePlotWidget.h"
#include "widgets/PlaybackScrubber.h"
#include "widgets/SafetyIndicator.h"

ResultsPanel::ResultsPanel(QWidget* parent) : QWidget(parent) {
    auto* outer = new QVBoxLayout(this);
    outer->setContentsMargins(0, 0, 0, 0);

    auto* scroll = new QScrollArea(this);
    scroll->setWidgetResizable(true);
    scroll->setFrameShape(QFrame::NoFrame);
    outer->addWidget(scroll);

    auto* content = new QWidget;
    auto* layout = new QVBoxLayout(content);
    layout->addWidget(buildSummary());
    layout->addWidget(buildComponentTable());
    layout->addWidget(buildPlots());
    layout->addWidget(buildPlayback());
    layout->addWidget(buildExport());
    layout->addStretch(1);
    scroll->setWidget(content);

    setMinimumWidth(320);
    clear();
}

QWidget* ResultsPanel::buildSummary() {
    auto* box = new QGroupBox(tr("Summary"), this);
    auto* layout = new QVBoxLayout(box);

    m_banner = new QLabel(box);
    m_banner->setAlignment(Qt::AlignCenter);
    m_banner->setFixedHeight(34);
    layout->addWidget(m_banner);

    auto* grid = new QGridLayout;
    auto makeStat = [box](const QString& caption, QLabel*& value) {
        auto* w = new QWidget(box);
        auto* v = new QVBoxLayout(w);
        v->setContentsMargins(2, 2, 2, 2);
        value = new QLabel("—", w);
        value->setStyleSheet(
            "font-size: 19px; font-weight: 600; color: #edf5ee;");
        auto* c = new QLabel(caption, w);
        c->setStyleSheet("color: #6b7d6c; font-size: 10px;");
        v->addWidget(value);
        v->addWidget(c);
        return w;
    };
    grid->addWidget(makeStat(tr("fall factor"), m_fallFactor), 0, 0);
    grid->addWidget(makeStat(tr("peak force"), m_peakForce), 0, 1);
    grid->addWidget(makeStat(tr("deceleration"), m_decel), 1, 0);
    grid->addWidget(makeStat(tr("elongation"), m_elongation), 1, 1);
    layout->addLayout(grid);

    m_scenario = new QLabel(box);
    m_scenario->setStyleSheet("color: #6b7d6c;");
    layout->addWidget(m_scenario);
    return box;
}

QWidget* ResultsPanel::buildComponentTable() {
    auto* box = new QGroupBox(tr("Component Safety"), this);
    auto* layout = new QVBoxLayout(box);
    m_table = new QTableWidget(0, 5, box);
    m_table->setHorizontalHeaderLabels(
        {"", tr("component"), tr("force"), tr("MBS"), tr("margin")});
    m_table->horizontalHeader()->setSectionResizeMode(1, QHeaderView::Stretch);
    m_table->verticalHeader()->setVisible(false);
    m_table->setEditTriggers(QAbstractItemView::NoEditTriggers);
    m_table->setSelectionMode(QAbstractItemView::NoSelection);
    m_table->setMinimumHeight(120);
    layout->addWidget(m_table);
    return box;
}

QWidget* ResultsPanel::buildPlots() {
    auto* box = new QGroupBox(tr("Curves"), this);
    auto* layout = new QVBoxLayout(box);

    layout->addWidget(new QLabel(tr("Force curve"), box));
    m_forcePlot = new ForcePlotWidget(box);
    m_forcePlot->setMinimumHeight(180);
    layout->addWidget(m_forcePlot);

    layout->addWidget(new QLabel(tr("Energy budget"), box));
    m_energyPlot = new ForcePlotWidget(box);
    m_energyPlot->setMinimumHeight(110);
    layout->addWidget(m_energyPlot);

    layout->addWidget(new QLabel(tr("Anchor distribution sweep"), box));
    m_anchorPlot = new ForcePlotWidget(box);
    m_anchorPlot->setMinimumHeight(160);
    layout->addWidget(m_anchorPlot);
    return box;
}

QWidget* ResultsPanel::buildPlayback() {
    auto* box = new QGroupBox(tr("Playback"), this);
    auto* layout = new QVBoxLayout(box);

    m_scrubber = new PlaybackScrubber(box);
    layout->addWidget(m_scrubber);

    auto* row = new QHBoxLayout;
    m_playBtn = new QPushButton(tr("▶ Play"), box);
    m_speed = new QComboBox(box);
    m_speed->addItem("0.1×", 0.1);
    m_speed->addItem("0.25×", 0.25);
    m_speed->addItem("0.5×", 0.5);
    m_speed->addItem("1×", 1.0);
    m_speed->setCurrentIndex(1);
    m_loop = new QCheckBox(tr("loop"), box);
    row->addWidget(m_playBtn);
    row->addWidget(m_speed);
    row->addWidget(m_loop);
    row->addStretch(1);
    layout->addLayout(row);
    return box;
}

QWidget* ResultsPanel::buildExport() {
    auto* box = new QGroupBox(tr("Export"), this);
    auto* row = new QHBoxLayout(box);
    auto* pdf = new QPushButton(tr("PDF Report"), box);
    auto* csv = new QPushButton(tr("CSV"), box);
    auto* copy = new QPushButton(tr("Copy Summary"), box);
    row->addWidget(pdf);
    row->addWidget(csv);
    row->addWidget(copy);
    connect(pdf, &QPushButton::clicked, this, &ResultsPanel::exportPdfRequested);
    connect(csv, &QPushButton::clicked, this, &ResultsPanel::exportCsvRequested);
    connect(copy, &QPushButton::clicked, this,
            &ResultsPanel::copySummaryRequested);
    return box;
}

void ResultsPanel::clear() {
    m_banner->setText(tr("no simulation yet"));
    m_banner->setStyleSheet(
        "background: #171c18; color: #6b7d6c; border-radius: 4px;");
    for (auto* l : {m_fallFactor, m_peakForce, m_decel, m_elongation})
        l->setText("—");
    m_scenario->clear();
    m_table->setRowCount(0);
    m_forcePlot->clear();
    m_energyPlot->clear();
    m_anchorPlot->clear();
    m_scrubber->setFrameCount(0);
}

void ResultsPanel::showResult(const SimulationResult& r) {
    // Banner
    const auto banner = r.computeBanner();
    const char* text = banner == SimulationResult::Banner::Safe      ? "SAFE"
                       : banner == SimulationResult::Banner::Caution ? "CAUTION"
                                                                     : "DANGER";
    const char* color = banner == SimulationResult::Banner::Safe ? "#7ecf45"
                        : banner == SimulationResult::Banner::Caution
                            ? "#e8b84b"
                            : "#e05050";
    m_banner->setText(text);
    m_banner->setStyleSheet(
        QStringLiteral(
            "background: %1; color: #0a0c0b; font-weight: 700; border-radius: 4px;")
            .arg(color));

    // Stats
    m_fallFactor->setText(QString::number(r.fallFactor, 'f', 2));
    m_peakForce->setText(QStringLiteral("%1 kN / %2 lbf")
                             .arg(r.peakForceKn, 0, 'f', 2)
                             .arg(r.peakForceKn * 224.809, 0, 'f', 0));
    m_decel->setText(QStringLiteral("%1 g").arg(r.decelerationG, 0, 'f', 1));
    m_elongation->setText(QStringLiteral("%1 m").arg(r.elongationM, 0, 'f', 2));
    m_scenario->setText(tr("scenario: %1").arg(r.scenarioType));

    // Component table
    m_table->setRowCount(static_cast<int>(r.components.size()));
    int row = 0;
    for (const auto& c : r.components) {
        auto* dot = new SafetyIndicator(m_table);
        dot->setLevel(c.status == ComponentSafety::Status::Safe
                          ? SafetyIndicator::Level::Safe
                      : c.status == ComponentSafety::Status::Caution
                          ? SafetyIndicator::Level::Caution
                          : SafetyIndicator::Level::Danger);
        auto* holder = new QWidget(m_table);
        auto* hl = new QHBoxLayout(holder);
        hl->setContentsMargins(0, 0, 0, 0);
        hl->setAlignment(Qt::AlignCenter);
        hl->addWidget(dot);
        m_table->setCellWidget(row, 0, holder);
        m_table->setItem(row, 1, new QTableWidgetItem(c.name));
        m_table->setItem(row, 2,
                         new QTableWidgetItem(
                             QStringLiteral("%1 kN").arg(c.forceKn, 0, 'f', 2)));
        m_table->setItem(row, 3,
                         new QTableWidgetItem(
                             QStringLiteral("%1 kN").arg(c.mbsKn, 0, 'f', 1)));
        m_table->setItem(row, 4,
                         new QTableWidgetItem(QStringLiteral("%1 %")
                                                  .arg(c.marginPct(), 0, 'f', 0)));
        ++row;
    }

    // Force curve with annotations
    m_forcePlot->clear();
    if (!r.forceCurve.empty()) {
        std::vector<double> times(r.forceCurve.size());
        for (size_t i = 0; i < times.size(); ++i) times[i] = i * r.forceCurveDtMs;
        m_forcePlot->plotForceCurve(times, r.forceCurve, tr("anchor total"));
        // annotate peak
        size_t peakIdx = 0;
        for (size_t i = 1; i < r.forceCurve.size(); ++i)
            if (r.forceCurve[i] > r.forceCurve[peakIdx]) peakIdx = i;
        m_forcePlot->addAnnotation(peakIdx * r.forceCurveDtMs, tr("peak"));
    }

    // Energy budget
    m_energyPlot->plotEnergyBudget(r.energyPotential, r.energyRope,
                                   r.energyBelay, r.energyResidual);

    // Playback
    m_scrubber->setFrameCount(static_cast<int>(r.replay.frames.size()));
    m_scrubber->setPeakFrame(r.replay.empty() ? -1 : r.replay.frameOfPeak());
}
