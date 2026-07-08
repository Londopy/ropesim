// gui-cpp/src/dialogs/ScenarioExportDialog.cpp

#include "dialogs/ScenarioExportDialog.h"

#include <QCheckBox>
#include <QDialogButtonBox>
#include <QFileDialog>
#include <QFormLayout>
#include <QLineEdit>
#include <QMessageBox>
#include <QPainter>
#include <QPdfWriter>
#include <QPushButton>
#include <QTextStream>

ScenarioExportDialog::ScenarioExportDialog(const SimulationResult& result,
                                           QWidget* parent)
    : QDialog(parent), m_result(result) {
    setWindowTitle(tr("Export"));
    auto* form = new QFormLayout(this);

    auto* pathRow = new QWidget(this);
    auto* h = new QHBoxLayout(pathRow);
    h->setContentsMargins(0, 0, 0, 0);
    m_path = new QLineEdit("ropesim_report.csv", pathRow);
    auto* browse = new QPushButton(tr("…"), pathRow);
    h->addWidget(m_path, 1);
    h->addWidget(browse);
    form->addRow(tr("File"), pathRow);
    connect(browse, &QPushButton::clicked, this, &ScenarioExportDialog::onBrowse);

    m_includeCurve = new QCheckBox(tr("Include force curve samples"), this);
    m_includeCurve->setChecked(true);
    m_includeComponents = new QCheckBox(tr("Include component table"), this);
    m_includeComponents->setChecked(true);
    form->addRow(QString(), m_includeCurve);
    form->addRow(QString(), m_includeComponents);

    auto* buttons = new QDialogButtonBox(
        QDialogButtonBox::Save | QDialogButtonBox::Cancel, this);
    connect(buttons, &QDialogButtonBox::accepted, this,
            &ScenarioExportDialog::onExport);
    connect(buttons, &QDialogButtonBox::rejected, this, &QDialog::reject);
    form->addRow(buttons);
}

void ScenarioExportDialog::onBrowse() {
    const QString f = QFileDialog::getSaveFileName(
        this, tr("Export"), m_path->text(),
        tr("CSV (*.csv);;PDF report (*.pdf)"));
    if (!f.isEmpty()) m_path->setText(f);
}

void ScenarioExportDialog::onExport() {
    const QString path = m_path->text();
    const bool ok = path.endsWith(".pdf", Qt::CaseInsensitive)
                        ? exportPdf(m_result, path)
                        : exportCsv(m_result, path);
    if (!ok) {
        QMessageBox::warning(this, tr("Export"), tr("Could not write %1").arg(path));
        return;
    }
    accept();
}

bool ScenarioExportDialog::exportCsv(const SimulationResult& r,
                                     const QString& path) {
    QFile file(path);
    if (!file.open(QIODevice::WriteOnly | QIODevice::Text)) return false;
    QTextStream out(&file);
    out << "key,value\n";
    out << "scenario," << r.scenarioType << "\n";
    out << "fall_factor," << r.fallFactor << "\n";
    out << "peak_force_kn," << r.peakForceKn << "\n";
    out << "deceleration_g," << r.decelerationG << "\n";
    out << "elongation_m," << r.elongationM << "\n";
    out << "energy_pe_j," << r.energyPotential << "\n";
    out << "energy_rope_j," << r.energyRope << "\n";
    out << "energy_belay_j," << r.energyBelay << "\n";
    out << "energy_residual_j," << r.energyResidual << "\n";
    out << "\ncomponent,force_kn,mbs_kn,margin_pct\n";
    for (const auto& c : r.components)
        out << c.name << "," << c.forceKn << "," << c.mbsKn << ","
            << c.marginPct() << "\n";
    if (!r.forceCurve.empty()) {
        out << "\ntime_ms,force_kn\n";
        for (size_t i = 0; i < r.forceCurve.size(); ++i)
            out << i * r.forceCurveDtMs << "," << r.forceCurve[i] << "\n";
    }
    return true;
}

bool ScenarioExportDialog::exportPdf(const SimulationResult& r,
                                     const QString& path) {
    QPdfWriter writer(path);
    writer.setPageSize(QPageSize(QPageSize::A4));
    QPainter p(&writer);
    if (!p.isActive()) return false;

    const int w = writer.width();
    int y = 300;
    auto line = [&](const QString& text, int size, bool bold = false) {
        QFont f = p.font();
        f.setPointSize(size);
        f.setBold(bold);
        p.setFont(f);
        p.drawText(QRect(300, y, w - 600, 400), Qt::AlignLeft, text);
        y += size * 55;
    };

    line("ropesim — simulation report", 20, true);
    line(QStringLiteral("scenario: %1").arg(r.scenarioType), 11);
    line(QStringLiteral("fall factor: %1").arg(r.fallFactor, 0, 'f', 2), 11);
    line(QStringLiteral("peak force: %1 kN").arg(r.peakForceKn, 0, 'f', 2), 11);
    line(QStringLiteral("deceleration: %1 g").arg(r.decelerationG, 0, 'f', 1), 11);
    line(QStringLiteral("elongation: %1 m").arg(r.elongationM, 0, 'f', 2), 11);
    y += 200;
    line("components", 13, true);
    for (const auto& c : r.components)
        line(QStringLiteral("%1 — %2 kN of %3 kN (margin %4 %)")
                 .arg(c.name)
                 .arg(c.forceKn, 0, 'f', 2)
                 .arg(c.mbsKn, 0, 'f', 1)
                 .arg(c.marginPct(), 0, 'f', 0),
             10);

    // Simple force curve sparkline
    if (!r.forceCurve.empty()) {
        y += 300;
        const QRect plot(300, y, w - 900, 2200);
        p.drawRect(plot);
        double peak = 0.001;
        for (double v : r.forceCurve) peak = std::max(peak, v);
        QPolygonF poly;
        for (size_t i = 0; i < r.forceCurve.size(); ++i) {
            poly << QPointF(
                plot.left() + plot.width() * static_cast<double>(i) /
                                  (r.forceCurve.size() - 1),
                plot.bottom() - plot.height() * (r.forceCurve[i] / peak));
        }
        p.setPen(QPen(QColor(58, 96, 32), 8));
        p.drawPolyline(poly);
    }
    return true;
}
