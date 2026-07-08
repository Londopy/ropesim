// gui-cpp/src/ui/AboutDialog.cpp

#include "ui/AboutDialog.h"

#include <QDialogButtonBox>
#include <QLabel>
#include <QVBoxLayout>

#include "core/RopeSimBridge.h"

AboutDialog::AboutDialog(QWidget* parent) : QDialog(parent) {
    setWindowTitle(tr("About ropesim"));
    auto* layout = new QVBoxLayout(this);

    auto* title = new QLabel(QStringLiteral("<h2>ropesim 3.0</h2>"), this);
    auto* body = new QLabel(
        tr("Climbing rope physics engine.<br><br>"
           "Native Qt6 frontend over a Rust physics core "
           "(UIAA 101 / EN 892 model, RK4 integration, Rapier3D).<br>"
           "Rust core ABI version: %1<br><br>"
           "<a href='https://github.com/Londopy/ropesim'>github.com/Londopy/ropesim</a> · "
           "<a href='https://londopy.github.io/ropesim/'>documentation</a><br><br>"
           "<i>For education and planning — never a substitute for judgement, "
           "testing, and redundancy at the crag.</i>")
            .arg(RopeSimBridge::abiVersion()),
        this);
    body->setOpenExternalLinks(true);
    body->setWordWrap(true);

    auto* buttons = new QDialogButtonBox(QDialogButtonBox::Close, this);
    connect(buttons, &QDialogButtonBox::rejected, this, &QDialog::reject);

    layout->addWidget(title);
    layout->addWidget(body);
    layout->addWidget(buttons);
}
