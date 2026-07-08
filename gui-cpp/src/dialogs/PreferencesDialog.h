// gui-cpp/src/dialogs/PreferencesDialog.h

#pragma once

#include <QDialog>

class QComboBox;
class QCheckBox;

class PreferencesDialog : public QDialog {
    Q_OBJECT
public:
    explicit PreferencesDialog(QWidget* parent = nullptr);

    // Persisted via QSettings
    static bool useImperialUnits();
    static double defaultGravity();

private:
    void save();
    QComboBox* m_units;
    QComboBox* m_gravity;
    QCheckBox* m_autoRun;
};
