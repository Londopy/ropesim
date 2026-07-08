// gui-cpp/src/core/RopeDatabase.h
//
// Reads / writes the shared ropes.json database (same file the Python
// library uses: ropesim/database/ropes.json).

#pragma once

#include <QString>
#include <QStringList>
#include <optional>
#include <vector>

/// Mirror of the Python RopeSpec pydantic model (JSON field names identical).
struct RopeSpec {
    QString name;
    QString manufacturer;
    QString ropeType = "single"; // single / half / twin
    double diameterMm = 9.8;
    double weightGPerM = 62.0;
    double impactForceKn = 8.5;
    int numberOfFalls = 7;
    double staticElongationPct = 8.0;
    double dynamicElongationPct = 33.0;
    double sheathPercentage = 38.0;
    double lengthM = 60.0;
    bool dryTreated = false;

    /// Length-normalised stiffness back-calculated from the EN 892 spec.
    double stiffnessKn() const;
};

class RopeDatabase {
public:
    /// Load from an explicit path, or discover ropes.json in known locations.
    explicit RopeDatabase(const QString& path = QString());

    bool load();
    bool save() const;

    const std::vector<RopeSpec>& ropes() const { return m_ropes; }
    QStringList ropeNames() const;
    std::optional<RopeSpec> findByName(const QString& name) const;
    void upsert(const RopeSpec& spec);

    QString path() const { return m_path; }
    QString lastError() const { return m_lastError; }

private:
    static QString discoverPath();
    QString m_path;
    QString m_lastError;
    std::vector<RopeSpec> m_ropes;
};
