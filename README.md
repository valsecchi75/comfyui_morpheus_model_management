# Morpheus Model Management

![Project Status: Alpha](https://img.shields.io/badge/Status-Alpha-orange) ![ComfyUI](https://img.shields.io/badge/Platform-ComfyUI-blue)

**Morpheus Model Management** is a ComfyUI custom node designed to introduce **structured, authenticated access to AI-generated talent catalogs**, combined with a metadata-driven identity layer for advanced image, editorial, and cinematic workflows.

The node does not operate as a static asset pack. It functions as a **control, governance, and orchestration layer** between ComfyUI pipelines and a remote talent repository, enabling consistent subject selection, filtering, and identity propagation across complex generation systems.

<img width="839" height="768" alt="image" src="https://github.com/user-attachments/assets/ebdd67df-f1eb-45f2-97b9-c75884f08303" />

---

## 🎯 What This Node Is (and Is Not)

| Morpheus Model Management IS... | Morpheus Model Management IS NOT... |
| :--- | :--- |
| ✅ A talent selection & identity management node | ❌ A marketplace for commercial models |
| ✅ A metadata-driven gateway to a remote archive | ❌ A preloaded model zoo |
| ✅ A system for maintaining subject consistency | ❌ A dataset redistribution tool |

---

## 🔐 Access Model & Authentication

**Morpheus Model Management does not ship with preloaded talents.**

All AI-generated talents are hosted remotely, protected behind an authentication layer, and delivered on-demand only after explicit authorization.

### Authentication Requirements
Access to the talent catalog requires:
1.  An active **[Patreon R&D Contract subscription](https://www.patreon.com/c/SergioValsecchi)**.
2.  Authentication performed **directly from the node UI**.
3.  Explicit user action to enable catalog access.

### UI-Level Access Visibility
The authentication state is always visible inside the node interface:

*   🔴 **Not Authenticated**: Catalog locked, "Connect with Patreon" banner displayed, no selectable talents.
*   🟢 **Authenticated**: Active account status, full catalog unlocked, filters/pagination enabled.

> **Note:** This guarantees transparent, enforceable access control at the node level, without relying on hidden configuration files.

---

## 📂 Talent Catalog Overview

The authenticated catalog currently includes **~900 AI-generated talents**, produced through hybrid pipelines including **FLUX, Z-Image, Nano Banana, Seedream**, and internal experimental systems.

Each talent entry includes:
*   Preview image
*   Structured metadata & descriptive tags
*   Internal talent identifier

Talents are retrieved on demand and may be cached locally for active sessions.

---

## ⚖️ Usage Scope & Legal Constraints

All talents are provided **exclusively for research, experimentation, testing, and internal R&D purposes**.

### ⚠️ Prohibited Uses & Limitations
*   **Commercial usage is explicitly prohibited.**
*   No ownership or likeness rights are transferred.
*   No endorsement or impersonation of real individuals is permitted.
*   Any resemblance to real persons is coincidental.

> **Neural Watermarking:**  
> All talents are protected with a **Neural Watermark** for traceability and misuse deterrence.

### 🛡️ Responsible Use & Minors Policy
Some talents represent **subjects under 18 years of age**. These entries are included **strictly for technical and research-oriented use** (pipeline validation, UI testing, dataset structuring).

> **CRITICAL:** Any misuse, sexualized depiction, or exploitative application is strictly forbidden. Responsibility for lawful and ethical usage lies entirely with the end user.

---

## 🎛️ Core Capabilities & UI

Once installed, the node appears under the **Morpheus** category in ComfyUI.

### Functional Capabilities
*   Authenticated access to remote archives.
*   Advanced filtering: *Name, Tags, Gender, Age Group, Ethnicity, Favorites*.
*   JSON-based data handling for automation.
*   Metadata propagation to downstream nodes.

### Key UI Elements
*   **Talent Gallery**: Paginated card-based layout.
*   ⭐ **Favorite**: Marks talents for prioritized recall.
*   ✏️ **Edit Metadata**: Inline editing of tags.
*   🖼️ **Fullscreen Preview**: Inspect facial structure and lighting.
*   📤 **Upload Talent**: Register custom AI-generated talents (Recommended format: 1:1 Square).

---

## 🔗 Workflow Integration Strategy

Morpheus acts as an **identity anchor node**. Once a talent is selected:
1.  Downstream nodes receive consistent identity metadata.
2.  Prompts remain bound to the same digital persona.
3.  Identity drift across variations is minimized.

**Compatible with:** FLUX Kontext pipelines, WAN-based editing, and LLM-driven prompt orchestration.

---

## 🛠️ Technical Architecture

*   **Language**: Python (ComfyUI Custom Node).
*   **Architecture**: Hybrid (Remote repository + Local metadata cache).
*   **Privacy**: No background downloads; assets retrieved only upon user action.

### JSON Metadata Schema
All talents follow a deterministic JSON schema:

```json
{
  "id": "model_047",
  "name": "Amara Solé",
  "gender": "female",
  "ethnicity": "mixed",
  "age_group": "young_adult",
  "usage_tags": ["editorial", "beauty", "commercial"],
  "data_path": "remote://morpheus/talents/amara_sole/",
  "metadata": {
    "style": "clean_editorial",
    "release_status": "alpha",
    "linked_lora": "amara_flux_v1"
  }
}
```
---

## 📥 Installation

### Manual Installation

1.  **Clone or Download**  
    Navigate to your ComfyUI custom nodes directory and clone the repository:
    ```bash
    cd ComfyUI/custom_nodes/
    git clone https://github.com/valsecchi75/comfyui_morpheus_model_management.git
    ```
    *(Alternatively, download the ZIP file and extract it into this folder).*

2.  **Restart**  
    Restart ComfyUI to load the new node category **Morpheus**.

---

## 🚀 Roadmap & Status

**Current Status:** ![Alpha](https://img.shields.io/badge/Status-Alpha-orange)

### 🎯 Focus Areas
*   Authentication stability & UI reliability.
*   Metadata integrity.
*   Access enforcement protocols.

### 🔮 Planned Developments
*   **Multi-user Support**: Team-based access control layers.
*   **Database Sync**: Centralized or hybrid synchronization strategies.
*   **API Integration**: REST APIs for external CMS / DAM systems.
*   **Auto-Training**: Experimental automation for LoRA generation (FLUX, WAN, Qwen).

### 📅 Upcoming Updates
- [ ] Limited random preview for non-subscribed users (basic node usage).
- [ ] Introduction of **100+ new AI-generated talents**.
- [ ] Bug fixes based on community feedback.
- [ ] Remote saving and synchronization of user-generated talents.
- [ ] Availability of dedicated **LoRA models** for all talents.
- [ ] **Multi-view representations** (Front, Profile, Variations).
- [ ] **Talent Blends**: Ability to combine multiple talents into a composite identity.


