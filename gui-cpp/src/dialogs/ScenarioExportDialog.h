// gui-cpp/src/dialogs/ScenarioExportDialog.h
//
// Export the current simulation result to CSV or a printable report.

#pragma once

#include <QDialog>

#include "core/SimulationResult.h"

class QCheckBox;
class QLineEdit;

class ScenarioExportDialog : public QDialog {
    Q_OBJECT
public:
    explicit ScenarioExportDialog(const SimulationResult& result,
                                  QWidget* parent = nullptr);

    static bool exportCsv(const SimulationResult& result, const QString& path);
    static bool exportPdf(const SimulationResult& result, const QString& path);

private:
    void onBrowse();
    void onExport();

    const SimulationResult& m_result;
    QLineEdit* m_path;
    QCheckBox* m_includeCurve;
    QCheckBox* m_includeComponents;
};
