// gui-cpp/src/widgets/PlaybackScrubber.cpp

#include "widgets/PlaybackScrubber.h"

#include <QMouseEvent>
#include <QPainter>

#include <algorithm>

PlaybackScrubber::PlaybackScrubber(QWidget* parent) : QWidget(parent) {
    setFixedHeight(26);
    setCursor(Qt::PointingHandCursor);
}

void PlaybackScrubber::setFrameCount(int count) {
    m_frames = std::max(count, 0);
    m_frame = std::min(m_frame, std::max(m_frames - 1, 0));
    update();
}

void PlaybackScrubber::setCurrentFrame(int frame) {
    m_frame = std::clamp(frame, 0, std::max(m_frames - 1, 0));
    update();
}

void PlaybackScrubber::setPeakFrame(int frame) {
    m_peakFrame = frame;
    update();
}

int PlaybackScrubber::frameAt(int x) const {
    if (m_frames < 2) return 0;
    const double t = std::clamp((x - 4.0) / (width() - 8.0), 0.0, 1.0);
    return static_cast<int>(t * (m_frames - 1) + 0.5);
}

void PlaybackScrubber::mousePressEvent(QMouseEvent* e) {
    if (m_frames > 0) {
        setCurrentFrame(frameAt(e->pos().x()));
        emit frameScrubbed(m_frame);
    }
}

void PlaybackScrubber::mouseMoveEvent(QMouseEvent* e) {
    if (e->buttons() & Qt::LeftButton && m_frames > 0) {
        setCurrentFrame(frameAt(e->pos().x()));
        emit frameScrubbed(m_frame);
    }
}

void PlaybackScrubber::paintEvent(QPaintEvent*) {
    QPainter p(this);
    p.setRenderHint(QPainter::Antialiasing);

    const QRectF track(4, height() / 2.0 - 3, width() - 8, 6);
    p.setPen(Qt::NoPen);
    p.setBrush(QColor(36, 43, 37));
    p.drawRoundedRect(track, 3, 3);

    if (m_frames > 1) {
        const double t = static_cast<double>(m_frame) / (m_frames - 1);
        // progress fill
        p.setBrush(QColor(58, 96, 32));
        p.drawRoundedRect(QRectF(track.left(), track.top(),
                                 track.width() * t, track.height()),
                          3, 3);
        // peak marker
        if (m_peakFrame >= 0 && m_peakFrame < m_frames) {
            const double tp = static_cast<double>(m_peakFrame) / (m_frames - 1);
            const double x = track.left() + track.width() * tp;
            p.setPen(QPen(QColor(224, 80, 80), 2));
            p.drawLine(QPointF(x, 3), QPointF(x, height() - 3));
        }
        // handle
        const double x = track.left() + track.width() * t;
        p.setPen(QPen(QColor(10, 12, 11), 1));
        p.setBrush(QColor(126, 207, 69));
        p.drawEllipse(QPointF(x, height() / 2.0), 7, 7);
    }
}
