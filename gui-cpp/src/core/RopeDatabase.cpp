// gui-cpp/src/core/RopeDatabase.cpp

#include "core/RopeDatabase.h"

#include <QCoreApplication>
#include <QDir>
#include <QFile>
#include <QFileInfo>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>

#include <cmath>

// EN 892 test parameters (mirrors _rustcore/src/physics.rs)
namespace {
constexpr double kG = 9.81;
constexpr double kEn892TestMassKg = 80.0;
constexpr double kEn892FallFactor = 1.772;
} // namespace

double RopeSpec::stiffnessKn() const {
    // Invert F = mg + sqrt((mg)^2 + 2*mg*ff*k)
    const double mg = kEn892TestMassKg * kG / 1000.0;
    const double f = std::max(impactForceKn, mg + 0.01);
    const double numerator = (f - mg) * (f - mg) - mg * mg;
    const double denominator = 2.0 * mg * kEn892FallFactor;
    if (denominator <= 0.0 || numerator <= 0.0) return 40.0;
    return std::max(numerator / denominator, 1.0);
}

RopeDatabase::RopeDatabase(const QString& path)
    : m_path(path.isEmpty() ? discoverPath() : path) {}

QString RopeDatabase::discoverPath() {
    const QStringList candidates = {
        QStringLiteral("../ropesim/database/ropes.json"),
        QStringLiteral("../../ropesim/database/ropes.json"),
        QCoreApplication::applicationDirPath() + "/assets/ropes.json",
        QStringLiteral("ropes.json"),
    };
    for (const auto& c : candidates) {
        if (QFile::exists(c)) return QDir(c).absolutePath().isEmpty() ? c : QFileInfo(c).absoluteFilePath();
    }
    return candidates.first();
}

bool RopeDatabase::load() {
    m_ropes.clear();
    QFile file(m_path);
    if (!file.open(QIODevice::ReadOnly)) {
        m_lastError = QStringLiteral("cannot open %1").arg(m_path);
        return false;
    }
    QJsonParseError err{};
    const auto doc = QJsonDocument::fromJson(file.readAll(), &err);
    if (err.error != QJsonParseError::NoError || !doc.isArray()) {
        m_lastError = QStringLiteral("invalid JSON: %1").arg(err.errorString());
        return false;
    }
    for (const auto& item : doc.array()) {
        const auto o = item.toObject();
        RopeSpec s;
        s.name = o.value("name").toString();
        s.manufacturer = o.value("manufacturer").toString();
        s.ropeType = o.value("rope_type").toString("single");
        s.diameterMm = o.value("diameter_mm").toDouble(9.8);
        s.weightGPerM = o.value("weight_gpm").toDouble(62.0);
        s.impactForceKn = o.value("impact_force_kn").toDouble(8.5);
        s.numberOfFalls = o.value("number_of_falls").toInt(7);
        s.staticElongationPct = o.value("static_elongation_pct").toDouble(8.0);
        s.dynamicElongationPct = o.value("dynamic_elongation_pct").toDouble(33.0);
        s.sheathPercentage = o.value("sheath_percentage").toDouble(38.0);
        s.lengthM = o.value("length_m").toDouble(60.0);
        s.dryTreated = o.value("dry_treated").toBool(false);
        if (!s.name.isEmpty()) m_ropes.push_back(std::move(s));
    }
    return true;
}

bool RopeDatabase::save() const {
    // Round-trip preserving the Python-side schema: re-read the original file
    // and only update/append entries we manage, so unknown fields survive.
    QJsonArray array;
    QFile in(m_path);
    if (in.open(QIODevice::ReadOnly)) {
        const auto doc = QJsonDocument::fromJson(in.readAll());
        if (doc.isArray()) array = doc.array();
        in.close();
    }

    auto findIndex = [&array](const QString& name) -> int {
        for (int i = 0; i < array.size(); ++i)
            if (array.at(i).toObject().value("name").toString() == name) return i;
        return -1;
    };

    for (const auto& s : m_ropes) {
        QJsonObject o;
        const int idx = findIndex(s.name);
        if (idx >= 0) o = array.at(idx).toObject();
        o["name"] = s.name;
        o["manufacturer"] = s.manufacturer;
        o["rope_type"] = s.ropeType;
        o["diameter_mm"] = s.diameterMm;
        o["weight_gpm"] = s.weightGPerM;
        o["impact_force_kn"] = s.impactForceKn;
        o["number_of_falls"] = s.numberOfFalls;
        o["static_elongation_pct"] = s.staticElongationPct;
        o["dynamic_elongation_pct"] = s.dynamicElongationPct;
        o["sheath_percentage"] = s.sheathPercentage;
        o["length_m"] = s.lengthM;
        o["dry_treated"] = s.dryTreated;
        if (!o.contains("standard")) o["standard"] = "EN 892 + UIAA 101";
        if (idx >= 0)
            array.replace(idx, o);
        else
            array.append(o);
    }

    QFile out(m_path);
    if (!out.open(QIODevice::WriteOnly | QIODevice::Truncate)) return false;
    out.write(QJsonDocument(array).toJson(QJsonDocument::Indented));
    return true;
}

QStringList RopeDatabase::ropeNames() const {
    QStringList names;
    names.reserve(static_cast<int>(m_ropes.size()));
    for (const auto& r : m_ropes) names << r.name;
    return names;
}

std::optional<RopeSpec> RopeDatabase::findByName(const QString& name) const {
    for (const auto& r : m_ropes)
        if (r.name == name) return r;
    return std::nullopt;
}

void RopeDatabase::upsert(const RopeSpec& spec) {
    for (auto& r : m_ropes) {
        if (r.name == spec.name) {
            r = spec;
            return;
        }
    }
    m_ropes.push_back(spec);
}
