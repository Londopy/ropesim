// gui-cpp/src/widgets/RopeSelector.h
//
// Searchable rope-database combo box with spec summary label.

#pragma once

#include <QWidget>

#include "core/RopeDatabase.h"

class QComboBox;
class QLabel;

class RopeSelector : public QWidget {
    Q_OBJECT
public:
    explicit RopeSelector(RopeDatabase* db, QWidget* parent = nullptr);

    std::optional<RopeSpec> currentRope() const;
    void refresh(); // re-read names from database
    void selectRope(const QString& name);

signals:
    void ropeChanged(const RopeSpec& spec);

private:
    void onIndexChanged(int idx);
    RopeDatabase* m_db;
    QComboBox* m_combo;
    QLabel* m_summary;
};
