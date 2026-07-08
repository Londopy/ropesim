// gui-cpp/src/main.cpp
//
// ropesim native GUI entry point.

#include <QApplication>
#include <QSurfaceFormat>

#include <cstdio>

#include "core/RopeSimBridge.h"
#include "ui/MainWindow.h"

int main(int argc, char** argv) {
    // OpenGL 4.1 core profile (macOS ceiling; fine on Windows/Linux)
    QSurfaceFormat fmt;
    fmt.setVersion(4, 1);
    fmt.setProfile(QSurfaceFormat::CoreProfile);
    fmt.setDepthBufferSize(24);
    fmt.setSamples(4);
    QSurfaceFormat::setDefaultFormat(fmt);

    QApplication app(argc, argv);
    QApplication::setApplicationName("ropesim");
    QApplication::setApplicationVersion("3.0.0");
    QApplication::setOrganizationName("ropesim");

    // Sanity-check the Rust core before showing any UI.
    const int abi = RopeSimBridge::abiVersion();
    if (abi != 3) {
        std::fprintf(stderr,
                     "ropesim core ABI mismatch: expected 3, got %d.\n"
                     "Rebuild the Rust core (cargo build --release).\n",
                     abi);
        return 1;
    }
    {
        RopeSimBridge bridge;
        const double ff = bridge.computeFallFactor(5.0, 2.82);
        std::printf("ropesim core OK (ABI %d, EN 892 test fall factor = %.3f)\n",
                    abi, ff);
    }

    MainWindow window;
    window.show();
    return app.exec();
}
