// gui-cpp/src/ui/ResultsPanel.h
//
// Right panel: summary numbers, component safety table, force curve,
// energy budget, anchor distribution, playback controls, export buttons.

#pragma once

#include <QWidget>

#include "core/SimulationResult.h"

class QComboBox;
class QCheckBox;
class QLabel;
class QPushButton;
class QTableWidget;
class ForcePlotWidget;
class PlaybackScrubber;

class ResultsPanel : public QWidget {
    Q_OBJECT
public:
    explicit ResultsPanel(QWidget* parent = nullptr);

    void showResult(const SimulationResult& result);
    void clear();

    // Playback wiring (MainWindow connects these to the viewport)
    PlaybackScrubber* scrubber() { return m_scrubber; }
    QPushButton* playButton() { return m_playBtn; }
    QComboBox* speedCombo() { return m_speed; }
    QCheckBox* loopCheck() { return m_loop; }

signals:
    void exportPdfRequested();
    void exportCsvRequested();
    void copySummaryRequested();

private:
    QWidget* buildSummary();
    QWidget* buildComponentTable();
    QWidget* buildPlots();
    QWidget* buildPlayback();
    QWidget* buildExport();

    QLabel* m_banner;
    QLabel* m_fallFactor;
    QLabel* m_peakForce;
    QLabel* m_decel;
    QLabel* m_elongation;
    QLabel* m_scenario;

    QTableWidget* m_table;
    ForcePlotWidget* m_forcePlot;
    ForcePlotWidget* m_energyPlot;
    ForcePlotWidget* m_anchorPlot;

    QPushButton* m_playBtn;
    PlaybackScrubber* m_scrubber;
    QComboBox* m_speed;
    QCheckBox* m_loop;
};
