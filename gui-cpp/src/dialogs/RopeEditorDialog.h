// gui-cpp/src/dialogs/RopeEditorDialog.h
//
// Add/edit a rope spec with live EN 892 / UIAA 101 compliance preview.

#pragma once

#include <QDialog>

#include "core/RopeDatabase.h"

class QCheckBox;
class QComboBox;
class QDoubleSpinBox;
class QLabel;
class QLineEdit;
class QSpinBox;

class RopeEditorDialog : public QDialog {
    Q_OBJECT
public:
    explicit RopeEditorDialog(RopeDatabase* db, QWidget* parent = nullptr);

    /// Pre-fill from an existing spec (edit mode).
    void loadSpec(const RopeSpec& spec);
    RopeSpec spec() const;

    void accept() override; // validates + saves to ropes.json

private:
    void updateCompliance();
    QLabel* complianceRow(const QString& text);

    RopeDatabase* m_db;
    QLineEdit* m_name;
    QLineEdit* m_manufacturer;
    QComboBox* m_type;
    QDoubleSpinBox* m_diameter;
    QDoubleSpinBox* m_weight;
    QDoubleSpinBox* m_impactForce;
    QSpinBox* m_falls;
    QDoubleSpinBox* m_staticElong;
    QDoubleSpinBox* m_dynamicElong;
    QDoubleSpinBox* m_sheath;
    QDoubleSpinBox* m_length;
    QCheckBox* m_dry;

    QLabel* m_cImpact;
    QLabel* m_cStatic;
    QLabel* m_cDynamic;
    QLabel* m_cFalls;
    QLabel* m_error;
};
