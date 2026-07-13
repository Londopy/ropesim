cmake_minimum_required(VERSION 3.25)
project(ropesim-gui VERSION 3.1.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_AUTOMOC ON)
set(CMAKE_AUTORCC ON)

# ── Dependencies ─────────────────────────────────────────────────────────────
find_package(Qt6 6.6 REQUIRED COMPONENTS Core Gui Widgets OpenGL OpenGLWidgets)

# glm: prefer system package, fall back to FetchContent
find_package(glm QUIET)
if(NOT glm_FOUND)
    include(FetchContent)
    FetchContent_Declare(glm
        GIT_REPOSITORY https://github.com/g-truc/glm.git
        GIT_TAG        1.0.1)
    FetchContent_MakeAvailable(glm)
endif()

# ── Rust core (cdylib built by cargo/maturin) ────────────────────────────────
# build.rs copies nothing automatically; locate the compiled library either in
# gui-cpp/lib/ (release packaging layout) or in the cargo target dir.
set(ROPESIM_CORE_NAMES _rustcore ropesim)
find_library(ROPESIM_CORE_LIB
    NAMES ${ROPESIM_CORE_NAMES}
    PATHS
        ${CMAKE_CURRENT_SOURCE_DIR}/lib
        ${CMAKE_CURRENT_SOURCE_DIR}/../target/release
        ${CMAKE_CURRENT_SOURCE_DIR}/../target/debug
    NO_DEFAULT_PATH)
# MSVC: cargo names the import library `_rustcore.dll.lib`, which
# find_library does not match — locate it explicitly.
if(WIN32 AND NOT ROPESIM_CORE_LIB)
    foreach(dir lib ../target/release ../target/debug)
        if(EXISTS ${CMAKE_CURRENT_SOURCE_DIR}/${dir}/_rustcore.dll.lib)
            set(ROPESIM_CORE_LIB ${CMAKE_CURRENT_SOURCE_DIR}/${dir}/_rustcore.dll.lib)
            set(ROPESIM_CORE_DLL ${CMAKE_CURRENT_SOURCE_DIR}/${dir}/_rustcore.dll)
            break()
        endif()
    endforeach()
endif()
if(NOT ROPESIM_CORE_LIB)
    message(FATAL_ERROR
        "Rust core library not found.\n"
        "Build it first:  cargo build --release --manifest-path ../ropesim/_rustcore/Cargo.toml\n"
        "then copy the resulting _rustcore shared library into gui-cpp/lib/")
endif()
message(STATUS "Rust core: ${ROPESIM_CORE_LIB}")

# ── Sources ──────────────────────────────────────────────────────────────────
set(SOURCES
    src/main.cpp
    src/core/RopeSimBridge.cpp
    src/core/SimulationResult.cpp
    src/core/RopeDatabase.cpp
    src/ui/MainWindow.cpp
    src/ui/Toolbar.cpp
    src/ui/PropertiesPanel.cpp
    src/ui/ResultsPanel.cpp
    src/ui/StatusBar.cpp
    src/ui/AboutDialog.cpp
    src/canvas/RouteCanvas2D.cpp
    src/canvas/Viewport3D.cpp
    src/dialogs/RopeEditorDialog.cpp
    src/dialogs/GearEditorDialog.cpp
    src/dialogs/ScenarioExportDialog.cpp
    src/dialogs/PreferencesDialog.cpp
    src/widgets/ForcePlotWidget.cpp
    src/widgets/RopeSelector.cpp
    src/widgets/SafetyIndicator.cpp
    src/widgets/PlaybackScrubber.cpp
    src/renderer/RopeRenderer.cpp
    src/renderer/GearRenderer.cpp
    src/renderer/RockFaceRenderer.cpp
    src/renderer/ForceArrowRenderer.cpp
)

# ── macOS: legacy AGL framework shim ─────────────────────────────────────────
# Recent macOS SDKs removed the deprecated AGL framework, but Qt6's OpenGL
# module still asks the linker for `-framework AGL`. Build a tiny stub so the
# linker is satisfied; harmless (and unused) on SDKs/Qt that don't need it.
if(APPLE)
    set(AGL_STUB_DIR ${CMAKE_BINARY_DIR}/_agl_stub)
    file(MAKE_DIRECTORY ${AGL_STUB_DIR}/AGL.framework)
    file(WRITE ${CMAKE_BINARY_DIR}/agl_stub.cpp
        "extern \"C\" void ropesim_agl_stub() {}\n")
    execute_process(
        COMMAND ${CMAKE_CXX_COMPILER} -dynamiclib -install_name @rpath/AGL
            ${CMAKE_BINARY_DIR}/agl_stub.cpp
            -o ${AGL_STUB_DIR}/AGL.framework/AGL
        RESULT_VARIABLE AGL_STUB_RC)
    if(AGL_STUB_RC EQUAL 0)
        add_link_options(-F${AGL_STUB_DIR})
        message(STATUS "AGL stub framework: ${AGL_STUB_DIR}")
    endif()
endif()

qt_add_executable(ropesim-gui ${SOURCES})

target_include_directories(ropesim-gui PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}/include
    ${CMAKE_CURRENT_SOURCE_DIR}/src)

target_link_libraries(ropesim-gui PRIVATE
    Qt6::Core Qt6::Gui Qt6::Widgets Qt6::OpenGL Qt6::OpenGLWidgets
    glm::glm
    ${ROPESIM_CORE_LIB})

# Ship shaders/assets next to the binary
add_custom_command(TARGET ropesim-gui POST_BUILD
    COMMAND ${CMAKE_COMMAND} -E copy_directory
        ${CMAKE_CURRENT_SOURCE_DIR}/shaders $<TARGET_FILE_DIR:ropesim-gui>/shaders
    COMMAND ${CMAKE_COMMAND} -E copy_directory
        ${CMAKE_CURRENT_SOURCE_DIR}/assets  $<TARGET_FILE_DIR:ropesim-gui>/assets)

# ── Tests ────────────────────────────────────────────────────────────────────
enable_testing()
add_executable(test_bridge tests/test_bridge.cpp src/core/RopeSimBridge.cpp)
target_include_directories(test_bridge PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}/include ${CMAKE_CURRENT_SOURCE_DIR}/src)
target_link_libraries(test_bridge PRIVATE glm::glm ${ROPESIM_CORE_LIB})
add_test(NAME bridge COMMAND test_bridge)

# Windows: the Rust DLL must sit next to the executables at runtime.
if(WIN32 AND ROPESIM_CORE_DLL)
    foreach(tgt ropesim-gui test_bridge)
        add_custom_command(TARGET ${tgt} POST_BUILD
            COMMAND ${CMAKE_COMMAND} -E copy_if_different
                ${ROPESIM_CORE_DLL} $<TARGET_FILE_DIR:${tgt}>)
    endforeach()
endif()
