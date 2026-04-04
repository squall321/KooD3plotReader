#include "app/DeepReportApp.hpp"
#include "app/DeepReportColors.hpp"
#include <imgui.h>
#include <implot.h>
#include <algorithm>
#include <cstdio>
#include <cmath>
#include <string>
#include <iostream>

// ============================================================
// 3D Viewer — shaders + colormap (private to this TU)
// ============================================================
static const char* VERT3D = R"(
#version 330 core
layout(location=0) in vec3 aPos;
layout(location=1) in vec3 aNorm;
layout(location=2) in float aFringe;
uniform mat4 uMVP;
uniform mat3 uNormalMat;
out vec3 vNorm;
out float vFringe;
void main() {
    gl_Position = uMVP * vec4(aPos, 1.0);
    vNorm = normalize(uNormalMat * aNorm);
    vFringe = aFringe;
}
)";

static const char* FRAG3D = R"(
#version 330 core
in vec3 vNorm;
in float vFringe;
uniform sampler1D uColormap;
uniform vec3 uLightDir;
uniform float uAmbient;
uniform int uUseFringe;
uniform vec3 uFlatColor;
out vec4 fragColor;
void main() {
    vec3 color;
    if (uUseFringe == 1)
        color = texture(uColormap, clamp(vFringe, 0.0, 1.0)).rgb;
    else
        color = uFlatColor;
    vec3 N = normalize(vNorm);
    float diff = abs(dot(N, uLightDir));
    color *= uAmbient + (1.0 - uAmbient) * diff;
    fragColor = vec4(color, 1.0);
}
)";

static void buildJetColormap(unsigned char* data) {
    for (int i = 0; i < 256; ++i) {
        float t = i / 255.0f;
        float r, g, b;
        if (t < 0.25f)      { r = 0; g = t/0.25f; b = 1; }
        else if (t < 0.5f)  { r = 0; g = 1; b = 1-(t-0.25f)/0.25f; }
        else if (t < 0.75f) { r = (t-0.5f)/0.25f; g = 1; b = 0; }
        else                { r = 1; g = 1-(t-0.75f)/0.25f; b = 0; }
        data[i*3+0] = (unsigned char)(r*255);
        data[i*3+1] = (unsigned char)(g*255);
        data[i*3+2] = (unsigned char)(b*255);
    }
}

void DeepReportApp::init3DViewer() {
    if (data_.d3plot_path.empty()) return;
    if (!sim3d_.loadMesh(data_.d3plot_path)) {
        std::cout << "[3D] Failed to load mesh: " << sim3d_.loadError << "\n";
        return;
    }
    std::cout << "[3D] Mesh: " << sim3d_.mesh.nodes.size() << " nodes, "
              << sim3d_.extFaces.size() << " exterior faces\n";

    sim3d_.loadStatesAsync(data_.d3plot_path, 4);

    shader3d_.loadFromString(VERT3D, FRAG3D);

    // Colormap texture
    glGenTextures(1, &colormapTex_);
    glBindTexture(GL_TEXTURE_1D, colormapTex_);
    unsigned char cmapData[256*3];
    buildJetColormap(cmapData);
    glTexImage1D(GL_TEXTURE_1D, 0, GL_RGB, 256, 0, GL_RGB, GL_UNSIGNED_BYTE, cmapData);
    glTexParameteri(GL_TEXTURE_1D, GL_TEXTURE_MIN_FILTER, GL_LINEAR);
    glTexParameteri(GL_TEXTURE_1D, GL_TEXTURE_MAG_FILTER, GL_LINEAR);
    glTexParameteri(GL_TEXTURE_1D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE);

    auto gpuFaces = sim3d_.buildGPUFaces();
    meshGPU_.build(sim3d_.initialCoords, gpuFaces);

    camera3d_.fitTo(meshGPU_.bboxMin[0], meshGPU_.bboxMin[1], meshGPU_.bboxMin[2],
                    meshGPU_.bboxMax[0], meshGPU_.bboxMax[1], meshGPU_.bboxMax[2]);

    mesh3dReady_ = true;
}

void DeepReportApp::ensureFBO(int w, int h) {
    if (w == fboW_ && h == fboH_ && fbo3d_) return;
    if (fbo3d_) { glDeleteFramebuffers(1, &fbo3d_); glDeleteTextures(1, &fboTex3d_); glDeleteRenderbuffers(1, &fboDepth3d_); }

    fboW_ = w; fboH_ = h;
    glGenFramebuffers(1, &fbo3d_);
    glBindFramebuffer(GL_FRAMEBUFFER, fbo3d_);

    glGenTextures(1, &fboTex3d_);
    glBindTexture(GL_TEXTURE_2D, fboTex3d_);
    glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, w, h, 0, GL_RGBA, GL_UNSIGNED_BYTE, nullptr);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR);
    glFramebufferTexture2D(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, GL_TEXTURE_2D, fboTex3d_, 0);

    glGenRenderbuffers(1, &fboDepth3d_);
    glBindRenderbuffer(GL_RENDERBUFFER, fboDepth3d_);
    glRenderbufferStorage(GL_RENDERBUFFER, GL_DEPTH24_STENCIL8, w, h);
    glFramebufferRenderbuffer(GL_FRAMEBUFFER, GL_DEPTH_STENCIL_ATTACHMENT, GL_RENDERBUFFER, fboDepth3d_);

    glBindFramebuffer(GL_FRAMEBUFFER, 0);
}

void DeepReportApp::setPresetView(int axis) {
    camera3d_.fitTo(meshGPU_.bboxMin[0], meshGPU_.bboxMin[1], meshGPU_.bboxMin[2],
                    meshGPU_.bboxMax[0], meshGPU_.bboxMax[1], meshGPU_.bboxMax[2]);
    constexpr float PI = 3.14159265f;
    switch (axis) {
        case 0: camera3d_.yaw = 0;       camera3d_.pitch = 0;      break;  // Front (-Z)
        case 1: camera3d_.yaw = PI;      camera3d_.pitch = 0;      break;  // Back (+Z)
        case 2: camera3d_.yaw = PI/2;    camera3d_.pitch = 0;      break;  // Right (+X)
        case 3: camera3d_.yaw = -PI/2;   camera3d_.pitch = 0;      break;  // Left (-X)
        case 4: camera3d_.yaw = 0;       camera3d_.pitch = PI/2-0.01f; break; // Top (+Y)
        case 5: camera3d_.yaw = 0;       camera3d_.pitch = -PI/2+0.01f; break; // Bottom (-Y)
    }
}

void DeepReportApp::render3DTab() {
    // Lazy init
    if (!mesh3dReady_ && !data_.d3plot_path.empty()) {
        static bool initAttempted = false;
        if (!initAttempted) {
            initAttempted = true;
            init3DViewer();
        }
    }

    if (!mesh3dReady_) {
        ImGui::TextColored(COL_DIM, "No d3plot path in result data (need result.json with d3plot_path)");
        ImGui::TextColored(COL_DIM, "Path: %s", data_.d3plot_path.c_str());
        return;
    }

    // Controls row
    const char* viewNames[] = {"Front", "Back", "Right", "Left", "Top", "Bottom"};
    for (int i = 0; i < 6; ++i) {
        if (i > 0) ImGui::SameLine();
        if (ImGui::Button(viewNames[i])) setPresetView(i);
    }
    ImGui::SameLine();
    ImGui::Checkbox("Fringe", &show3DFringe_);
    ImGui::SameLine();
    ImGui::Checkbox("Wire", &wireframe3d_);

    if (sim3d_.statesLoaded && sim3d_.numStates() > 0) {
        ImGui::SameLine();
        if (ImGui::Button(playing3d_ ? "Pause" : "Play")) playing3d_ = !playing3d_;
        ImGui::SameLine();
        ImGui::SetNextItemWidth(200);
        ImGui::SliderInt("##state3d", &current3DState_, 0, sim3d_.numStates() - 1);
        ImGui::SameLine();
        ImGui::Text("t=%.6f", sim3d_.stateTime(current3DState_));

        // Playback
        if (playing3d_) {
            playTimer3d_ += ImGui::GetIO().DeltaTime;
            if (playTimer3d_ > 1.0f / 30.0f) {
                playTimer3d_ = 0;
                current3DState_ = (current3DState_ + 1) % sim3d_.numStates();
            }
        }

        // Update mesh
        auto coords = sim3d_.getDeformedCoords(current3DState_);
        std::vector<float> fringe;
        if (show3DFringe_) fringe = sim3d_.getVonMisesFringe(current3DState_);
        meshGPU_.updatePositions(coords, fringe);
    } else if (!sim3d_.statesLoaded) {
        ImGui::SameLine();
        ImGui::TextColored(COL_DIM, "Loading states...");
    }

    // Render to FBO
    ImVec2 avail = ImGui::GetContentRegionAvail();
    int vpW = std::max(100, (int)avail.x);
    int vpH = std::max(100, (int)avail.y);
    ensureFBO(vpW, vpH);

    // Mouse interaction on viewport
    ImVec2 vpPos = ImGui::GetCursorScreenPos();
    ImGui::InvisibleButton("##3dvp", avail);
    bool vpHovered = ImGui::IsItemHovered();

    if (vpHovered) {
        ImGuiIO& io = ImGui::GetIO();
        if (ImGui::IsMouseDragging(ImGuiMouseButton_Left)) {
            ImVec2 d = io.MouseDelta;
            camera3d_.orbit(-d.x * 0.005f, -d.y * 0.005f);
        }
        if (ImGui::IsMouseDragging(ImGuiMouseButton_Middle)) {
            ImVec2 d = io.MouseDelta;
            camera3d_.pan(-d.x, d.y);
        }
        if (io.MouseWheel != 0)
            camera3d_.zoom(io.MouseWheel > 0 ? 0.9f : 1.1f);
    }

    camera3d_.aspect = (float)vpW / vpH;
    camera3d_.update();

    // Render to FBO
    glBindFramebuffer(GL_FRAMEBUFFER, fbo3d_);
    glViewport(0, 0, vpW, vpH);
    glClearColor(0.08f, 0.08f, 0.14f, 1.0f);
    glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT);
    glEnable(GL_DEPTH_TEST);

    if (wireframe3d_) glPolygonMode(GL_FRONT_AND_BACK, GL_LINE);

    shader3d_.use();
    shader3d_.setMat4("uMVP", camera3d_.mvp);
    shader3d_.setMat3("uNormalMat", camera3d_.normalMat);
    shader3d_.setVec3("uLightDir", 0.3f, 0.8f, 0.5f);
    shader3d_.setFloat("uAmbient", 0.3f);
    shader3d_.setInt("uUseFringe", show3DFringe_ ? 1 : 0);

    glActiveTexture(GL_TEXTURE0);
    glBindTexture(GL_TEXTURE_1D, colormapTex_);
    shader3d_.setInt("uColormap", 0);

    for (size_t i = 0; i < meshGPU_.partCount(); ++i) {
        const auto& p = meshGPU_.part(i);
        if (!p.visible) continue;
        if (!show3DFringe_)
            shader3d_.setVec3("uFlatColor", p.color[0], p.color[1], p.color[2]);
        glBindVertexArray(p.vao);
        glDrawElements(GL_TRIANGLES, p.indexCount, GL_UNSIGNED_INT, nullptr);
    }

    if (wireframe3d_) glPolygonMode(GL_FRONT_AND_BACK, GL_FILL);
    glBindFramebuffer(GL_FRAMEBUFFER, 0);

    // Draw FBO texture as ImGui image
    ImGui::SetCursorScreenPos(vpPos);
    ImGui::Image((ImTextureID)(intptr_t)fboTex3d_, avail, ImVec2(0,1), ImVec2(1,0));
}

