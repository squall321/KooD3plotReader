#include "app/SphereReportApp.hpp"
#include <imgui.h>
#include <filesystem>
#include <iostream>
#include <cstdlib>
#include <cmath>
#include <algorithm>

namespace fs = std::filesystem;

// ── Shaders (same as DeepReportTab3D) ──────────────────────
static const char* VERT_DETAIL = R"(
#version 330 core
layout(location=0) in vec3 aPos;
layout(location=1) in vec3 aNorm;
layout(location=2) in float aFringe;
uniform mat4  uMVP;
uniform mat3  uNormalMat;
uniform int   uSectionEnabled;
uniform int   uSectionAxis;
uniform float uSectionPos;
out vec3  vNorm;
out float vFringe;
void main() {
    gl_Position = uMVP * vec4(aPos, 1.0);
    vNorm   = normalize(uNormalMat * aNorm);
    vFringe = aFringe;
    float coord = (uSectionAxis == 0) ? aPos.x
                : (uSectionAxis == 1) ? aPos.y
                :                       aPos.z;
    gl_ClipDistance[0] = (uSectionEnabled == 1) ? (uSectionPos - coord) : 1.0;
}
)";

static const char* FRAG_DETAIL = R"(
#version 330 core
in vec3 vNorm;
in float vFringe;
uniform sampler1D uColormap;
uniform vec3  uLightDir;
uniform float uAmbient;
uniform int   uUseFringe;
uniform vec3  uFlatColor;
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

static const char* VERT_DPLANE = R"(
#version 330 core
layout(location=0) in vec3 aPos;
uniform mat4 uMVP;
void main() { gl_Position = uMVP * vec4(aPos, 1.0); }
)";

static const char* FRAG_DPLANE = R"(
#version 330 core
uniform vec4 uColor;
out vec4 fragColor;
void main() { fragColor = uColor; }
)";

// ============================================================
// Path helpers
// ============================================================
std::string SphereReportApp::getRunOutputDir(int angleIdx) const {
    if (angleIdx < 0 || angleIdx >= (int)data_.results.size()) return "";
    if (data_.test_dir.empty()) return "";
    fs::path out = fs::path(data_.test_dir) / "output" / data_.results[angleIdx].run_folder;
    return out.string();
}

std::string SphereReportApp::getRunD3plotPath(int angleIdx) const {
    std::string dir = getRunOutputDir(angleIdx);
    if (dir.empty()) return "";
    fs::path p = fs::path(dir) / "d3plot";
    if (fs::exists(p)) return p.string();
    return "";
}

// ============================================================
// Init 3D viewer resources
// ============================================================
void SphereReportApp::initDetailViewer() {
    if (detailShader_.id != 0) return;
    detailShader_.loadFromString(VERT_DETAIL, FRAG_DETAIL);
    detailPlaneShader_.loadFromString(VERT_DPLANE, FRAG_DPLANE);

    // Jet colormap texture
    glGenTextures(1, &detailColormapTex_);
    glBindTexture(GL_TEXTURE_1D, detailColormapTex_);
    unsigned char cmap[256*3];
    for (int i = 0; i < 256; ++i) {
        float t = i / 255.0f;
        float r, g, b;
        if      (t < 0.25f) { r = 0;               g = t/0.25f;            b = 1; }
        else if (t < 0.50f) { r = 0;               g = 1;                  b = 1-(t-0.25f)/0.25f; }
        else if (t < 0.75f) { r = (t-0.5f)/0.25f;  g = 1;                  b = 0; }
        else                { r = 1;                g = 1-(t-0.75f)/0.25f;  b = 0; }
        cmap[i*3+0] = (unsigned char)(r*255);
        cmap[i*3+1] = (unsigned char)(g*255);
        cmap[i*3+2] = (unsigned char)(b*255);
    }
    glTexImage1D(GL_TEXTURE_1D, 0, GL_RGB, 256, 0, GL_RGB, GL_UNSIGNED_BYTE, cmap);
    glTexParameteri(GL_TEXTURE_1D, GL_TEXTURE_MIN_FILTER, GL_LINEAR);
    glTexParameteri(GL_TEXTURE_1D, GL_TEXTURE_MAG_FILTER, GL_LINEAR);
    glTexParameteri(GL_TEXTURE_1D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE);

    // Cut plane quad VAO
    glGenVertexArrays(1, &detailPlaneVAO_);
    glGenBuffers(1, &detailPlaneVBO_);
    glBindVertexArray(detailPlaneVAO_);
    glBindBuffer(GL_ARRAY_BUFFER, detailPlaneVBO_);
    glBufferData(GL_ARRAY_BUFFER, 4 * 3 * sizeof(float), nullptr, GL_DYNAMIC_DRAW);
    glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, 0, nullptr);
    glEnableVertexAttribArray(0);
    glBindVertexArray(0);
}

void SphereReportApp::ensureDetailFBO(int w, int h) {
    if (w == detailFBOW_ && h == detailFBOH_ && detailFBO_) return;
    if (detailFBO_) {
        glDeleteFramebuffers(1, &detailFBO_);
        glDeleteTextures(1, &detailFBOTex_);
        glDeleteRenderbuffers(1, &detailFBODepth_);
    }
    detailFBOW_ = w; detailFBOH_ = h;
    glGenFramebuffers(1, &detailFBO_);
    glBindFramebuffer(GL_FRAMEBUFFER, detailFBO_);
    glGenTextures(1, &detailFBOTex_);
    glBindTexture(GL_TEXTURE_2D, detailFBOTex_);
    glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA8, w, h, 0, GL_RGBA, GL_UNSIGNED_BYTE, nullptr);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR);
    glFramebufferTexture2D(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, GL_TEXTURE_2D, detailFBOTex_, 0);
    glGenRenderbuffers(1, &detailFBODepth_);
    glBindRenderbuffer(GL_RENDERBUFFER, detailFBODepth_);
    glRenderbufferStorage(GL_RENDERBUFFER, GL_DEPTH24_STENCIL8, w, h);
    glFramebufferRenderbuffer(GL_FRAMEBUFFER, GL_DEPTH_STENCIL_ATTACHMENT, GL_RENDERBUFFER, detailFBODepth_);
    glBindFramebuffer(GL_FRAMEBUFFER, 0);
}

// ============================================================
// Load d3plot for a specific angle
// ============================================================
void SphereReportApp::loadAngleD3plot(int angleIdx) {
    if (angleIdx < 0 || angleIdx >= (int)data_.results.size()) return;
    std::string d3path = getRunD3plotPath(angleIdx);
    if (d3path.empty()) {
        std::cerr << "[AngleDetail] No d3plot for " << data_.results[angleIdx].run_folder << "\n";
        detailLoaded_ = false;
        return;
    }

    std::cout << "[AngleDetail] Loading: " << d3path << "\n";
    detailSim_ = std::make_unique<SimData>();
    if (!detailSim_->loadMesh(d3path)) {
        std::cerr << "[AngleDetail] Failed: " << detailSim_->loadError << "\n";
        detailLoaded_ = false;
        return;
    }

    // Build GPU mesh
    auto gpuFaces = detailSim_->buildGPUFaces();
    detailMeshGPU_ = MeshGPU();
    detailMeshGPU_.build(detailSim_->initialCoords, gpuFaces);

    detailCamera_ = Camera();
    detailCamera_.fitTo(detailMeshGPU_.bboxMin[0], detailMeshGPU_.bboxMin[1], detailMeshGPU_.bboxMin[2],
                        detailMeshGPU_.bboxMax[0], detailMeshGPU_.bboxMax[1], detailMeshGPU_.bboxMax[2]);

    // Load states with 2GB memory budget (auto stride)
    detailSim_->loadStatesBudgeted(d3path, 2048);

    detailState_ = 0;
    detailAngleIdx_ = angleIdx;
    detailLoaded_ = true;
    std::cout << "[AngleDetail] Mesh loaded, states loading async...\n";
}

// ============================================================
// Launch LSPrePost
// ============================================================
void SphereReportApp::launchLSPrePost(int angleIdx) {
    std::string dir = getRunOutputDir(angleIdx);
    if (dir.empty()) return;

    std::string lspp;
    const char* candidates[] = {
        "installed/lsprepost/lspp412_mesa",
        "/opt/lsprepost/lspp412_mesa",
        nullptr
    };
    for (int i = 0; candidates[i]; ++i)
        if (fs::exists(candidates[i])) { lspp = candidates[i]; break; }

    if (lspp.empty()) {
        std::cerr << "[LSPrePost] Binary not found\n";
        return;
    }

    fs::path d3plot = fs::path(dir) / "d3plot";
    std::string cmd = lspp + " " + d3plot.string() + " &";
    std::cout << "[LSPrePost] " << cmd << "\n";
    (void)std::system(cmd.c_str());
}

// ============================================================
// Batch section render trigger (A method)
// ============================================================
void SphereReportApp::triggerBatchSectionRender(int angleIdx, int axis, int partId) {
    std::string dir = getRunOutputDir(angleIdx);
    if (dir.empty()) { batchRenderStatus_ = "Error: no output dir"; return; }

    std::string axisStr = (axis == 0) ? "x" : (axis == 1) ? "y" : "z";
    // Build unified_analyzer section-view command
    std::string cmd = "unified_analyzer";
    cmd += " --output " + dir;
    cmd += " --section-view";
    cmd += " --section-view-axes " + axisStr;
    if (partId > 0)
        cmd += " --section-view-target-ids " + std::to_string(partId);
    cmd += " " + (fs::path(dir) / "d3plot").string();
    cmd += " &";

    batchRenderActive_ = true;
    batchRenderStatus_ = "Rendering " + axisStr + "-axis section for "
                        + data_.results[angleIdx].angle.name + "...";
    std::cout << "[BatchRender] " << cmd << "\n";
    (void)std::system(cmd.c_str());
}

// ============================================================
// Angle Detail Tab
// ============================================================
void SphereReportApp::renderAngleDetail() {
    if (data_.test_dir.empty()) {
        ImGui::TextColored(COL_DIM,
            "test_dir not set in report.json.\n"
            "Regenerate report with latest koo_sphere_report to enable this tab.");
        return;
    }

    auto& results = data_.results;
    if (results.empty()) { ImGui::Text("No angle data."); return; }

    // ── Angle selector ────────────────────────────────────────
    int current = detailAngleIdx_;
    if (current < 0 && !selectedAngles_.empty())
        current = *selectedAngles_.begin();
    if (current < 0) current = 0;

    ImGui::SetNextItemWidth(250);
    if (ImGui::BeginCombo("Angle##detail",
            (current >= 0 && current < (int)results.size())
            ? results[current].angle.name.c_str() : "--")) {
        for (int i = 0; i < (int)results.size(); ++i) {
            bool sel = (i == current);
            if (ImGui::Selectable(results[i].angle.name.c_str(), sel))
                current = i;
        }
        ImGui::EndCombo();
    }

    std::string d3path = getRunD3plotPath(current);
    bool hasD3plot = !d3path.empty();
    ImGui::SameLine();
    if (hasD3plot)
        ImGui::TextColored(COL_ACCENT, "d3plot found");
    else
        ImGui::TextColored(COL_RED, "d3plot not found");

    if (hasD3plot) {
        ImGui::SameLine();
        if (ImGui::Button("Load 3D##detail")) {
            initDetailViewer();
            loadAngleD3plot(current);
        }
    }

    ImGui::Separator();

    // ── Action buttons row ────────────────────────────────────
    if (hasD3plot) {
        if (ImGui::Button("Open LSPrePost"))
            launchLSPrePost(current);
        ImGui::SameLine();

        ImGui::TextColored(COL_DIM, "|");
        ImGui::SameLine();
        ImGui::Text("Section Render:");
        ImGui::SameLine();
        const char* axNames[] = {"X", "Y", "Z"};
        ImGui::SetNextItemWidth(60);
        ImGui::Combo("##batchAx", &batchRenderAxis_, axNames, 3);
        ImGui::SameLine();

        ImGui::SetNextItemWidth(150);
        if (ImGui::BeginCombo("##batchPart",
                batchRenderPartId_ == 0 ? "All Parts" :
                data_.parts.count(batchRenderPartId_) ?
                    data_.parts.at(batchRenderPartId_).name.c_str() : "All Parts")) {
            if (ImGui::Selectable("All Parts", batchRenderPartId_ == 0))
                batchRenderPartId_ = 0;
            for (auto& [pid, pi] : data_.parts) {
                char lbl[128];
                snprintf(lbl, sizeof(lbl), "%d: %s", pid, pi.name.c_str());
                if (ImGui::Selectable(lbl, pid == batchRenderPartId_))
                    batchRenderPartId_ = pid;
            }
            ImGui::EndCombo();
        }
        ImGui::SameLine();
        if (ImGui::Button("Render##batch"))
            triggerBatchSectionRender(current, batchRenderAxis_, batchRenderPartId_);

        if (!batchRenderStatus_.empty()) {
            ImGui::SameLine();
            ImGui::TextColored(COL_YELLOW, "%s", batchRenderStatus_.c_str());
        }
    }

    ImGui::Spacing();
    ImGui::Separator();

    // ── 3D Section View ───────────────────────────────────────
    if (!detailLoaded_ || detailAngleIdx_ != current) {
        if (hasD3plot)
            ImGui::TextColored(COL_DIM, "Click 'Load 3D' to view this angle's simulation in 3D.");
        else
            ImGui::TextColored(COL_DIM, "d3plot not available for this angle.");
        return;
    }

    // Controls row
    ImGui::Checkbox("Fringe##det", &detailFringe_);
    ImGui::SameLine();
    ImGui::Checkbox("Section##det", &detailSection_);
    if (detailSection_) {
        ImGui::SameLine();
        ImGui::RadioButton("X##ds", &detailSectionAxis_, 0); ImGui::SameLine();
        ImGui::RadioButton("Y##ds", &detailSectionAxis_, 1); ImGui::SameLine();
        ImGui::RadioButton("Z##ds", &detailSectionAxis_, 2); ImGui::SameLine();
        ImGui::SetNextItemWidth(200);
        ImGui::SliderFloat("##dsPos", &detailSectionPos_, 0.0f, 1.0f, "");
        ImGui::SameLine();
        float bmin = detailMeshGPU_.bboxMin[detailSectionAxis_];
        float bmax = detailMeshGPU_.bboxMax[detailSectionAxis_];
        float wp = bmin + detailSectionPos_ * (bmax - bmin);
        const char* an = (detailSectionAxis_==0) ? "X" : (detailSectionAxis_==1) ? "Y" : "Z";
        ImGui::TextColored(COL_ACCENT, "%s=%.2f", an, wp);
    }

    // Part focus
    ImGui::SameLine();
    ImGui::SetNextItemWidth(130);
    if (ImGui::BeginCombo("Focus##detPart",
            detailPartFilter_ == 0 ? "All" :
            data_.parts.count(detailPartFilter_) ?
                data_.parts.at(detailPartFilter_).name.c_str() : "All")) {
        if (ImGui::Selectable("All##detAll", detailPartFilter_ == 0))
            detailPartFilter_ = 0;
        for (auto& [pid, pi] : data_.parts) {
            char lbl[128];
            snprintf(lbl, sizeof(lbl), "%d: %s", pid, pi.name.c_str());
            if (ImGui::Selectable(lbl, pid == detailPartFilter_))
                detailPartFilter_ = pid;
        }
        ImGui::EndCombo();
    }

    // Time slider + play
    int nStates = detailSim_->numStates();
    bool statesReady = detailSim_->statesLoaded.load();
    if (statesReady && nStates > 0) {
        ImGui::SameLine();
        if (ImGui::Button(detailPlaying_ ? "||##dp" : ">##dp"))
            detailPlaying_ = !detailPlaying_;
        ImGui::SameLine();
        ImGui::SetNextItemWidth(200);
        ImGui::SliderInt("##detSt", &detailState_, 0, std::max(0, nStates - 1));
        ImGui::SameLine();
        ImGui::Text("t=%.6f", detailSim_->stateTime(detailState_));

        if (detailPlaying_) {
            detailPlayTimer_ += ImGui::GetIO().DeltaTime;
            if (detailPlayTimer_ > 1.0f / 30.0f) {
                detailPlayTimer_ = 0;
                detailState_ = (detailState_ + 1) % std::max(1, nStates);
            }
        }

        // Update mesh deformation + fringe
        auto coords = detailSim_->getDeformedCoords(detailState_);
        std::vector<float> fringe;
        if (detailFringe_) fringe = detailSim_->getVonMisesFringe(detailState_);
        detailMeshGPU_.updatePositions(coords, fringe);
    } else if (!statesReady) {
        ImGui::SameLine();
        ImGui::TextColored(COL_DIM, "Loading states... %d%%",
            (int)(detailSim_->statesProgress.load()));
    }

    // ── Render to FBO ─────────────────────────────────────────
    ImVec2 avail = ImGui::GetContentRegionAvail();
    int vpW = std::max(100, (int)avail.x);
    int vpH = std::max(100, (int)avail.y);
    ensureDetailFBO(vpW, vpH);

    // Mouse interaction
    ImVec2 vpPos = ImGui::GetCursorScreenPos();
    ImGui::InvisibleButton("##detVP", avail);
    bool vpHovered = ImGui::IsItemHovered();

    if (vpHovered) {
        auto& io = ImGui::GetIO();
        if (ImGui::IsMouseDragging(ImGuiMouseButton_Left))
            detailCamera_.orbit(-io.MouseDelta.x * 0.005f, -io.MouseDelta.y * 0.005f);
        if (ImGui::IsMouseDragging(ImGuiMouseButton_Middle))
            detailCamera_.pan(-io.MouseDelta.x, io.MouseDelta.y);
        if (io.MouseWheel != 0)
            detailCamera_.zoom(io.MouseWheel > 0 ? 0.9f : 1.1f);
    }

    detailCamera_.aspect = (float)vpW / vpH;
    detailCamera_.update();

    // Section world pos
    float sectionWorldPos = 0;
    if (detailSection_) {
        float bmin = detailMeshGPU_.bboxMin[detailSectionAxis_];
        float bmax = detailMeshGPU_.bboxMax[detailSectionAxis_];
        sectionWorldPos = bmin + detailSectionPos_ * (bmax - bmin);
    }

    glBindFramebuffer(GL_FRAMEBUFFER, detailFBO_);
    glViewport(0, 0, vpW, vpH);
    glClearColor(0.08f, 0.08f, 0.14f, 1.0f);
    glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT);
    glEnable(GL_DEPTH_TEST);

    if (detailSection_) glEnable(GL_CLIP_DISTANCE0);

    detailShader_.use();
    detailShader_.setMat4("uMVP", detailCamera_.mvp);
    detailShader_.setMat3("uNormalMat", detailCamera_.normalMat);
    detailShader_.setVec3("uLightDir", 0.3f, 0.8f, 0.5f);
    detailShader_.setFloat("uAmbient", 0.3f);
    detailShader_.setInt("uUseFringe", detailFringe_ ? 1 : 0);
    detailShader_.setInt("uSectionEnabled", detailSection_ ? 1 : 0);
    detailShader_.setInt("uSectionAxis", detailSectionAxis_);
    detailShader_.setFloat("uSectionPos", sectionWorldPos);

    glActiveTexture(GL_TEXTURE0);
    glBindTexture(GL_TEXTURE_1D, detailColormapTex_);
    detailShader_.setInt("uColormap", 0);

    for (size_t i = 0; i < detailMeshGPU_.partCount(); ++i) {
        const auto& p = detailMeshGPU_.part(i);
        if (!p.visible) continue;

        float brightness = 1.0f;
        if (detailPartFilter_ != 0 && p.partId != detailPartFilter_)
            brightness = 0.25f;

        if (!detailFringe_) {
            float r = p.color[0], g = p.color[1], b = p.color[2];
            detailShader_.setVec3("uFlatColor", r * brightness, g * brightness, b * brightness);
        } else {
            // In fringe mode, brightness modulates ambient
            detailShader_.setFloat("uAmbient", 0.3f * brightness);
        }

        glBindVertexArray(p.vao);
        glDrawElements(GL_TRIANGLES, p.indexCount, GL_UNSIGNED_INT, nullptr);
    }
    // Reset ambient
    detailShader_.setFloat("uAmbient", 0.3f);

    if (detailSection_) {
        glDisable(GL_CLIP_DISTANCE0);

        // Draw cut plane indicator quad
        float ext = 0.02f;
        float x0 = detailMeshGPU_.bboxMin[0] - ext*(detailMeshGPU_.bboxMax[0]-detailMeshGPU_.bboxMin[0]);
        float x1 = detailMeshGPU_.bboxMax[0] + ext*(detailMeshGPU_.bboxMax[0]-detailMeshGPU_.bboxMin[0]);
        float y0 = detailMeshGPU_.bboxMin[1] - ext*(detailMeshGPU_.bboxMax[1]-detailMeshGPU_.bboxMin[1]);
        float y1 = detailMeshGPU_.bboxMax[1] + ext*(detailMeshGPU_.bboxMax[1]-detailMeshGPU_.bboxMin[1]);
        float z0 = detailMeshGPU_.bboxMin[2] - ext*(detailMeshGPU_.bboxMax[2]-detailMeshGPU_.bboxMin[2]);
        float z1 = detailMeshGPU_.bboxMax[2] + ext*(detailMeshGPU_.bboxMax[2]-detailMeshGPU_.bboxMin[2]);
        float sp = sectionWorldPos;
        float quad[4][3];
        if (detailSectionAxis_ == 0) {
            quad[0][0]=sp; quad[0][1]=y0; quad[0][2]=z0;
            quad[1][0]=sp; quad[1][1]=y1; quad[1][2]=z0;
            quad[2][0]=sp; quad[2][1]=y1; quad[2][2]=z1;
            quad[3][0]=sp; quad[3][1]=y0; quad[3][2]=z1;
        } else if (detailSectionAxis_ == 1) {
            quad[0][0]=x0; quad[0][1]=sp; quad[0][2]=z0;
            quad[1][0]=x1; quad[1][1]=sp; quad[1][2]=z0;
            quad[2][0]=x1; quad[2][1]=sp; quad[2][2]=z1;
            quad[3][0]=x0; quad[3][1]=sp; quad[3][2]=z1;
        } else {
            quad[0][0]=x0; quad[0][1]=y0; quad[0][2]=sp;
            quad[1][0]=x1; quad[1][1]=y0; quad[1][2]=sp;
            quad[2][0]=x1; quad[2][1]=y1; quad[2][2]=sp;
            quad[3][0]=x0; quad[3][1]=y1; quad[3][2]=sp;
        }
        glBindBuffer(GL_ARRAY_BUFFER, detailPlaneVBO_);
        glBufferSubData(GL_ARRAY_BUFFER, 0, sizeof(quad), quad);

        detailPlaneShader_.use();
        detailPlaneShader_.setMat4("uMVP", detailCamera_.mvp);
        glBindVertexArray(detailPlaneVAO_);

        glEnable(GL_BLEND);
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA);
        glDepthMask(GL_FALSE);
        glUniform4f(glGetUniformLocation(detailPlaneShader_.id, "uColor"),
                    0.25f, 0.65f, 1.0f, 0.18f);
        glDrawArrays(GL_TRIANGLE_FAN, 0, 4);

        glUniform4f(glGetUniformLocation(detailPlaneShader_.id, "uColor"),
                    0.25f, 0.75f, 1.0f, 0.85f);
        glLineWidth(1.5f);
        glDrawArrays(GL_LINE_LOOP, 0, 4);
        glLineWidth(1.0f);

        glDepthMask(GL_TRUE);
        glDisable(GL_BLEND);
        glBindVertexArray(0);
    }

    glBindFramebuffer(GL_FRAMEBUFFER, 0);

    // Display
    ImGui::SetCursorScreenPos(vpPos);
    ImGui::Image((ImTextureID)(intptr_t)detailFBOTex_, avail, ImVec2(0,1), ImVec2(1,0));
}
