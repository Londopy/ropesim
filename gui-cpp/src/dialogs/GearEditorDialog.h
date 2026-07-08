// gui-cpp/src/dialogs/GearEditorDialog.h
//
// Edit a placed gear piece: type, MBS, placement quality, orientation.

#pragma once

#include <QDialog>
#include <glm/vec3.hpp>

class QComboBox;
class QDoubleSpinBox;

struct GearEditResult {
    int gearType = 1; // 1 bolt, 2 cam, 3 nut (PlacementMode values)
    double mbsKn = 25.0;
    double quality = 1.0;
    glm::vec3 pullDir{0.0f, -1.0f, 0.0f};
};

class GearEditorDialog : public QDialog {
    Q_OBJECT
public:
    explicit GearEditorDialog(QWidget* parent = nullptr);
    void load(const GearEditResult& g);
    GearEditResult result() const;

private:
    QComboBox* m_type;
    QDoubleSpinBox* m_mbs;
    QDoubleSpinBox* m_quality;
    QDoubleSpinBox *m_dirX, *m_dirY, *m_dirZ;
};
