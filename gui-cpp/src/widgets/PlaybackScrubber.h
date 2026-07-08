// gui-cpp/src/widgets/PlaybackScrubber.h
//
// Draggable timeline for simulation playback, with a peak-force marker.

#pragma once

#include <QWidget>

class PlaybackScrubber : public QWidget {
    Q_OBJECT
public:
    explicit PlaybackScrubber(QWidget* parent = nullptr);

    void setFrameCount(int count);
    void setCurrentFrame(int frame);
    void setPeakFrame(int frame); // annotated marker
    int currentFrame() const { return m_frame; }

signals:
    void frameScrubbed(int frame);

protected:
    void paintEvent(QPaintEvent*) override;
    void mousePressEvent(QMouseEvent* e) override;
    void mouseMoveEvent(QMouseEvent* e) override;

private:
    int frameAt(int x) const;
    int m_frames = 0;
    int m_frame = 0;
    int m_peakFrame = -1;
};
