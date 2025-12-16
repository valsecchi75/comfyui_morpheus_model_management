import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";

const SUPABASE_FUNCTIONS_URL = "https://hrlwqnqqgcxxezagyfah.supabase.co/functions/v1";

const MorpheusGalleryNode = {
    name: "MorpheusModelManagement",
    isLoading: false,
    currentPage: 1,
    totalPages: 1,
    deviceId: null,

    async getDeviceId() {
        if (this.deviceId) return this.deviceId;
        try {
            const response = await api.fetchApi("/morpheus/device_id");
            const data = await response.json();
            this.deviceId = data.device_id;
            return this.deviceId;
        } catch (e) {
            this.deviceId = "local-" + Math.random().toString(36).substring(2, 15);
            return this.deviceId;
        }
    },

    async getTalents(catalogPath, imagesFolder, filters = {}, page = 1) {
        this.isLoading = true;
        try {
            const deviceId = await this.getDeviceId();
            const params = new URLSearchParams({
                catalog_path: catalogPath,
                images_folder: imagesFolder,
                page: page,
                page_size: 8,
                name: filters.name || "",
                tags: filters.tags || "",
                logic: filters.logic || "OR",
                gender: filters.gender || "",
                age_group: filters.age_group || "",
                ethnicity: filters.ethnicity || "",
                favorites_only: filters.favorites_only || false,
                use_remote: "true",
                device_id: deviceId
            });

            const response = await api.fetchApi(`/morpheus/talents?${params}`);
            const data = await response.json();
            
            this.totalPages = data.total_pages || 1;
            this.currentPage = data.current_page || 1;
            return data;
        } catch (error) {
            console.error("Morpheus: Error fetching talents:", error);
            return { talents: [], total_pages: 1, current_page: 1, total_count: 0, authenticated: false };
        } finally {
            this.isLoading = false;
        }
    },

    async setUiState(nodeId, galleryId, state) {
        try {
            await api.fetchApi("/morpheus/ui_state", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ 
                    node_id: nodeId, 
                    gallery_id: galleryId,
                    state: state 
                }),
            });
        } catch(e) {
            console.error("Morpheus: Failed to set UI state", e);
        }
    },

    async getUiState(nodeId, galleryId) {
        try {
            const response = await api.fetchApi(`/morpheus/ui_state?node_id=${nodeId}&gallery_id=${galleryId}`);
            return await response.json();
        } catch(e) {
            console.error("Morpheus: Failed to get UI state", e);
            return {
                selected_talent_id: "",
                license_key: "",
                license_email: "",
                filters: {
                    name: "",
                    tags: "",
                    logic: "OR",
                    gender: "",
                    age_group: "",
                    ethnicity: "",
                    favorites_only: false
                }
            };
        }
    },

    setup(nodeType, nodeData) {
        const onNodeCreated = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function () {
            const result = onNodeCreated?.apply(this, arguments);

            if (!this.properties || !this.properties.morpheus_gallery_id) {
                if (!this.properties) { this.properties = {}; }
                this.properties.morpheus_gallery_id = "morpheus-gallery-" + Math.random().toString(36).substring(2, 11);
            }

            // Hidden widget for gallery ID
            const galleryIdWidget = this.addWidget(
                "text",
                "morpheus_gallery_id_widget",
                this.properties.morpheus_gallery_id,
                () => {},
                {}
            );
            galleryIdWidget.serializeValue = () => this.properties.morpheus_gallery_id;
            galleryIdWidget.draw = function() {};
            galleryIdWidget.computeSize = function() { return [0, -4]; };

            // Hidden widget for selected talent ID
            const selectionWidget = this.addWidget(
                "text",
                "selected_talent_id",
                this.properties.selected_talent_id || "",
                () => {},
                { multiline: false }
            );
            selectionWidget.serializeValue = () => this.properties.selected_talent_id || "";
            selectionWidget.draw = function() {};
            selectionWidget.computeSize = function() { return [0, -4]; };

            const MIN_NODE_WIDTH = 700;
            const HEADER_HEIGHT = 90;
            this.size = [700, 600];

            // Current state
            this.selectedTalentId = "";
            this.filters = {
                name: "",
                tags: "",
                logic: "OR",
                gender: "",
                age_group: "",
                ethnicity: "",
                favorites_only: false
            };

            const node_instance = this;
            const widgetContainer = document.createElement("div");
            widgetContainer.className = "morpheus-container-wrapper";
            this.addDOMWidget("gallery", "div", widgetContainer, {});

            const uniqueId = `morpheus-gallery-${this.id}`;
            widgetContainer.innerHTML = `
                <style>
                    #${uniqueId} .morpheus-container { display: flex; flex-direction: column; height: 100%; font-family: sans-serif; }
                    #${uniqueId} .morpheus-selected-preview { flex-shrink: 0; padding: 10px; background-color: #1a1a1a; border-radius: 5px; margin-bottom: 10px; }
                    #${uniqueId} .morpheus-preview-image { width: 120px; height: 120px; object-fit: cover; border-radius: 8px; background-color: #333; margin-right: 10px; }
                    #${uniqueId} .morpheus-preview-info { flex-grow: 1; display: flex; flex-direction: column; justify-content: center; }
                    #${uniqueId} .morpheus-preview-name { font-size: 16px; font-weight: bold; margin-bottom: 5px; color: #fff; }
                    #${uniqueId} .morpheus-preview-tags { font-size: 12px; color: #ccc; }
                    #${uniqueId} .morpheus-controls { display: flex; flex-direction: column; padding: 5px; gap: 8px; flex-shrink: 0; }
                    #${uniqueId} .morpheus-controls-row { display: flex; gap: 10px; align-items: center; }
                    #${uniqueId} .morpheus-controls-row input, #${uniqueId} .morpheus-controls-row select {
                        background: #222; color: #ccc; border: 1px solid #555; padding: 4px; border-radius: 4px; font-size: 12px;
                    }
                    #${uniqueId} .morpheus-controls-row button {
                        background: #555; color: #fff; border: 1px solid #666; padding: 4px 8px; border-radius: 4px; cursor: pointer; font-size: 12px;
                    }
                    #${uniqueId} .morpheus-controls-row button:hover { background: #666; }
                    #${uniqueId} .morpheus-gallery { flex-grow: 1; overflow-y: auto; background-color: #1a1a1a; padding: 10px; display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 12px; align-content: start; border-radius: 5px; }
                    @media (max-width: 600px) {
                        #${uniqueId} .morpheus-gallery { grid-template-columns: repeat(auto-fill, minmax(120px, 1fr)); gap: 8px; }
                        #${uniqueId} .morpheus-media-container { height: 120px; }
                    }
                    #${uniqueId} .morpheus-gallery::-webkit-scrollbar { width: 8px; }
                    #${uniqueId} .morpheus-gallery::-webkit-scrollbar-track { background: #2a2a2a; border-radius: 4px; }
                    #${uniqueId} .morpheus-gallery::-webkit-scrollbar-thumb { background-color: #555; border-radius: 4px; }
                    #${uniqueId} .morpheus-talent-card { cursor: pointer; border: 3px solid transparent; border-radius: 8px; background-color: var(--comfy-input-bg); transition: all 0.3s ease; display: flex; flex-direction: column; position: relative; overflow: hidden; }
                    #${uniqueId} .morpheus-talent-card.selected { border-color: #00FFC9; box-shadow: 0 0 8px rgba(0, 255, 201, 0.5); }
                    #${uniqueId} .morpheus-talent-card:hover { border-color: #555; }
                    #${uniqueId} .morpheus-selection-badge {
                        position: absolute; top: 5px; right: 5px; background-color: rgba(0, 255, 201, 0.9);
                        color: #000; font-weight: bold; width: 24px; height: 24px; border-radius: 50%;
                        display: flex; align-items: center; justify-content: center; font-size: 14px;
                        z-index: 2; border: 1px solid #000; opacity: 0; transition: opacity 0.3s ease;
                    }
                    #${uniqueId} .morpheus-talent-card.selected .morpheus-selection-badge { opacity: 1; }
                    #${uniqueId} .morpheus-media-container {
                        width: 100%; height: 160px; background-color: #111; overflow: hidden; 
                        display: flex; align-items: center; justify-content: center; position: relative;
                    }
                    #${uniqueId} .morpheus-media-container img { width: 100%; height: 100%; object-fit: cover; }
                    #${uniqueId} .morpheus-talent-info { padding: 8px; flex-grow: 1; display: flex; flex-direction: column; }
                    #${uniqueId} .morpheus-talent-name { font-size: 12px; font-weight: bold; margin-bottom: 4px; color: var(--node-text-color); text-align: center; }
                    #${uniqueId} .morpheus-talent-tags { display: flex; flex-wrap: wrap; gap: 3px; margin-top: 4px; }
                    #${uniqueId} .morpheus-talent-tags .tag { background-color: #006699; color: #fff; padding: 2px 4px; font-size: 10px; border-radius: 3px; }
                    #${uniqueId} .morpheus-favorite-star { 
                        position: absolute; bottom: 8px; left: 8px; font-size: 18px; cursor: pointer; 
                        color: #666; transition: all 0.2s; z-index: 10; 
                        background: rgba(0,0,0,0.8); width: 28px; height: 28px; border-radius: 50%;
                        display: flex; align-items: center; justify-content: center;
                        text-shadow: 0 0 4px rgba(0,0,0,0.9);
                    }
                    #${uniqueId} .morpheus-favorite-star.active { 
                        color: #FFD700; background: rgba(255,215,0,0.2); 
                        text-shadow: 0 0 6px rgba(255, 215, 0, 0.8);
                        border: 1px solid rgba(255,215,0,0.5);
                    }
                    #${uniqueId} .morpheus-favorite-star:hover { 
                        color: #FFD700; background: rgba(255,215,0,0.1); 
                        transform: scale(1.1);
                    }
                    #${uniqueId} .morpheus-loading { text-align: center; padding: 20px; color: #ccc; }
                    #${uniqueId} .morpheus-pagination { display: flex; justify-content: center; gap: 10px; padding: 10px; flex-shrink: 0; }
                    #${uniqueId} .morpheus-pagination button { padding: 6px 12px; }
                    #${uniqueId} .tag-logic-btn {
                        padding: 4px 8px; background-color: #555; color: #fff; border: 1px solid #666;
                        border-radius: 4px; cursor: pointer; flex-shrink: 0;
                    }
                    #${uniqueId} .tag-logic-btn:hover { background-color: #666; }
                    .morpheus-fullscreen-zoom {
                        position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.95);
                        display: flex; align-items: center; justify-content: center; z-index: 20000;
                        opacity: 0; transition: opacity 0.3s ease;
                    }
                    .morpheus-fullscreen-zoom.active { opacity: 1; }
                    .morpheus-fullscreen-zoom .zoom-image {
                        max-width: 90vw; max-height: 90vh; object-fit: contain;
                        border-radius: 8px; box-shadow: 0 8px 32px rgba(0,0,0,0.8);
                    }
                    .morpheus-fullscreen-zoom .zoom-nav {
                        position: absolute; top: 50%; transform: translateY(-50%);
                        background: rgba(255,255,255,0.1); border: 1px solid rgba(255,255,255,0.2);
                        color: white; width: 50px; height: 50px; border-radius: 50%;
                        display: flex; align-items: center; justify-content: center;
                        cursor: pointer; font-size: 20px; font-weight: bold;
                        transition: all 0.3s ease; backdrop-filter: blur(10px);
                    }
                    .morpheus-fullscreen-zoom .zoom-nav:hover {
                        background: rgba(255,255,255,0.2); transform: translateY(-50%) scale(1.1);
                    }
                    .morpheus-fullscreen-zoom .zoom-nav.prev { left: 20px; }
                    .morpheus-fullscreen-zoom .zoom-nav.next { right: 20px; }
                    .morpheus-fullscreen-zoom .zoom-close {
                        position: absolute; top: 20px; right: 20px;
                        background: rgba(255,255,255,0.1); border: 1px solid rgba(255,255,255,0.2);
                        color: white; width: 40px; height: 40px; border-radius: 50%;
                        display: flex; align-items: center; justify-content: center;
                        cursor: pointer; font-size: 18px; font-weight: bold;
                        transition: all 0.3s ease; backdrop-filter: blur(10px);
                    }
                    .morpheus-fullscreen-zoom .zoom-close:hover {
                        background: rgba(255,100,100,0.3); transform: scale(1.1);
                    }
                    .morpheus-fullscreen-zoom .zoom-title {
                        position: absolute; bottom: 20px; left: 50%; transform: translateX(-50%);
                        color: white; font-size: 16px; font-weight: bold;
                        background: rgba(0,0,0,0.7); padding: 8px 16px; border-radius: 20px;
                        backdrop-filter: blur(10px);
                    }
                    .morpheus-upload-card {
                        border: 2px dashed #666; background: #2a2a2a; cursor: pointer;
                        transition: all 0.3s ease; position: relative;
                    }
                    .morpheus-upload-card:hover {
                        border-color: #888; background: #333;
                    }
                    .morpheus-upload-card .upload-content {
                        display: flex; flex-direction: column; align-items: center;
                        justify-content: center; height: 100%; padding: 20px;
                        color: #aaa; text-align: center;
                    }
                    .morpheus-upload-card .upload-icon {
                        font-size: 48px; margin-bottom: 10px; color: #666;
                    }
                    .morpheus-upload-card .upload-text {
                        font-size: 14px; font-weight: bold;
                    }
                    .morpheus-upload-card .upload-hint {
                        font-size: 12px; color: #888; margin-top: 5px;
                    }
                    
                    /* Talent action buttons */
                    #${uniqueId} .talent-actions {
                        position: absolute; top: 8px; left: 8px; display: flex; gap: 4px;
                        opacity: 0; transition: opacity 0.3s ease; z-index: 3;
                    }
                    #${uniqueId} .morpheus-talent-card:hover .talent-actions {
                        opacity: 1;
                    }
                    #${uniqueId} .action-btn {
                        width: 26px; height: 26px; border-radius: 4px; border: none;
                        display: flex; align-items: center; justify-content: center;
                        font-size: 14px; cursor: pointer; transition: all 0.2s ease;
                    }
                    #${uniqueId} .action-btn.edit {
                        background: rgba(0, 123, 255, 0.8); color: white;
                    }
                    #${uniqueId} .action-btn.edit:hover {
                        background: rgba(0, 123, 255, 1);
                    }
                    #${uniqueId} .action-btn.delete {
                        background: rgba(220, 53, 69, 0.8); color: white;
                    }
                    #${uniqueId} .action-btn.delete:hover {
                        background: rgba(220, 53, 69, 1);
                    }
                </style>
                <div id="${uniqueId}" style="height: 100%;">
                    <div class="morpheus-container">
                        <div class="morpheus-selected-preview" style="display: flex; align-items: center;">
                            <img class="morpheus-preview-image" src="" alt="Selected Talent" style="display: none;">
                            <div class="morpheus-preview-info">
                                <div class="morpheus-preview-name">No talent selected</div>
                                <div class="morpheus-preview-tags"></div>
                            </div>
                        </div>
                        
                        <div class="morpheus-patreon-section" style="padding: 8px; background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%); border-radius: 5px; margin-bottom: 8px; border: 1px solid #f96854;">
                            <div style="display: flex; gap: 8px; align-items: center; justify-content: space-between;">
                                <div style="display: flex; align-items: center; gap: 8px;">
                                    <span style="font-size: 16px;">🅿️</span>
                                    <span class="patreon-status-text" style="font-size: 11px; color: #f96854;">Connect with Patreon for exclusive content</span>
                                </div>
                                <div style="display: flex; gap: 6px;">
                                    <button class="patreon-connect-btn" style="background: #f96854; color: #fff; border: none; padding: 5px 12px; border-radius: 4px; cursor: pointer; font-size: 11px; font-weight: bold;">Connect Patreon</button>
                                    <button class="patreon-check-btn" style="background: #444; color: #fff; border: 1px solid #666; padding: 5px 8px; border-radius: 4px; cursor: pointer; font-size: 11px; display: none;">Check Status</button>
                                    <button class="patreon-logout-btn" style="background: #666; color: #fff; border: none; padding: 5px 8px; border-radius: 4px; cursor: pointer; font-size: 11px; display: none;">Logout</button>
                                </div>
                            </div>
                            <div class="patreon-membership-status" style="font-size: 10px; margin-top: 5px; color: #888; display: none;"></div>
                        </div>
                        
                        <div class="morpheus-controls">
                            <div class="morpheus-controls-row">
                                <label style="font-size: 12px;">Name:</label>
                                <input type="text" class="name-filter" placeholder="Filter by name..." style="flex-grow: 1;">
                                <label style="font-size: 12px;">Tags:</label>
                                <input type="text" class="tags-filter" placeholder="brunette,blonde,casual..." style="flex-grow: 1;">
                                <button class="tag-logic-btn">OR</button>
                            </div>
                            
                            <div class="morpheus-controls-row">
                                <label style="font-size: 12px; display: flex; align-items: center; cursor: pointer;">
                                    <input type="checkbox" class="favorites-filter" style="margin-right: 5px;">
                                    Favorites ★
                                </label>
                                <button class="refresh-btn" style="margin-left: auto; padding: 4px 8px; font-size: 12px;">🔄 Refresh</button>
                            </div>
                            
                            <div class="morpheus-controls-row">
                                <label style="font-size: 12px;">Gender:</label>
                                <select class="gender-filter">
                                    <option value="">All</option>
                                    <option value="male">Male</option>
                                    <option value="female">Female</option>
                                    <option value="non_binary">Non-binary</option>
                                    <option value="other">Other</option>
                                </select>
                                <label style="font-size: 12px;">Age:</label>
                                <select class="age-filter">
                                    <option value="">All</option>
                                    <option value="child">Child</option>
                                    <option value="teen">Teen</option>
                                    <option value="young_adult">Young Adult</option>
                                    <option value="adult">Adult</option>
                                    <option value="mature">Mature</option>
                                    <option value="senior">Senior</option>
                                </select>
                                <label style="font-size: 12px;">Ethnicity:</label>
                                <select class="ethnicity-filter">
                                    <option value="">All</option>
                                    <option value="caucasian">Caucasian</option>
                                    <option value="african">African</option>
                                    <option value="asian">Asian</option>
                                    <option value="hispanic">Hispanic</option>
                                    <option value="mixed">Mixed</option>
                                    <option value="middle_eastern">Middle Eastern</option>
                                    <option value="other">Other</option>
                                </select>
                            </div>
                        </div>
                        
                        <div class="morpheus-gallery">
                            <div class="morpheus-loading">Loading talents...</div>
                        </div>
                        
                        <div class="morpheus-pagination">
                            <button class="prev-page-btn" disabled>← Previous</button>
                            <span class="page-info">Page 1 of 1</span>
                            <button class="next-page-btn" disabled>Next →</button>
                        </div>
                    </div>
                </div>
            `;

            // Get DOM elements
            const mainContainer = widgetContainer.querySelector(".morpheus-container");
            const galleryEl = widgetContainer.querySelector(".morpheus-gallery");
            const previewImage = widgetContainer.querySelector(".morpheus-preview-image");
            const previewName = widgetContainer.querySelector(".morpheus-preview-name");
            const previewTags = widgetContainer.querySelector(".morpheus-preview-tags");
            const nameFilter = widgetContainer.querySelector(".name-filter");
            const tagsFilter = widgetContainer.querySelector(".tags-filter");
            const tagLogicBtn = widgetContainer.querySelector(".tag-logic-btn");
            const favoritesFilter = widgetContainer.querySelector(".favorites-filter");
            const genderFilter = widgetContainer.querySelector(".gender-filter");
            const ageFilter = widgetContainer.querySelector(".age-filter");
            const ethnicityFilter = widgetContainer.querySelector(".ethnicity-filter");
            const prevPageBtn = widgetContainer.querySelector(".prev-page-btn");
            const nextPageBtn = widgetContainer.querySelector(".next-page-btn");
            const pageInfo = widgetContainer.querySelector(".page-info");
            const refreshBtn = widgetContainer.querySelector(".refresh-btn");

            // Patreon integration elements
            const patreonConnectBtn = widgetContainer.querySelector(".patreon-connect-btn");
            const patreonCheckBtn = widgetContainer.querySelector(".patreon-check-btn");
            const patreonLogoutBtn = widgetContainer.querySelector(".patreon-logout-btn");
            const patreonStatusText = widgetContainer.querySelector(".patreon-status-text");
            const patreonMembershipStatus = widgetContainer.querySelector(".patreon-membership-status");

            const updatePatreonUI = (status) => {
                if (status.authenticated) {
                    patreonCheckBtn.style.display = "inline-block";
                    patreonLogoutBtn.style.display = "inline-block";
                    
                    if (status.expired) {
                        // Token expired - show reconnect button prominently
                        patreonConnectBtn.style.display = "inline-block";
                        patreonConnectBtn.textContent = "Reconnect";
                        patreonConnectBtn.style.background = "#ffaa00";
                        patreonStatusText.textContent = `Session expired for ${status.user_name || status.user_email || 'Patron'} - please reconnect`;
                        patreonStatusText.style.color = "#ffaa00";
                    } else {
                        // Valid connection - hide connect button
                        patreonConnectBtn.style.display = "none";
                        patreonConnectBtn.textContent = "Connect Patreon";
                        patreonConnectBtn.style.background = "#f96854";
                        patreonStatusText.textContent = `Connected as ${status.user_name || status.user_email || 'Patron'}`;
                        patreonStatusText.style.color = "#00ff88";
                    }
                } else {
                    // Not authenticated - show connect button
                    patreonConnectBtn.style.display = "inline-block";
                    patreonConnectBtn.textContent = "Connect Patreon";
                    patreonConnectBtn.style.background = "#f96854";
                    patreonCheckBtn.style.display = "none";
                    patreonLogoutBtn.style.display = "none";
                    patreonStatusText.textContent = "Connect with Patreon for exclusive content";
                    patreonStatusText.style.color = "#f96854";
                    patreonMembershipStatus.style.display = "none";
                }
            };

            const checkPatreonStatus = async () => {
                try {
                    const deviceId = await MorpheusGalleryNode.getDeviceId();
                    const response = await fetch(`${SUPABASE_FUNCTIONS_URL}/patreon-status?device_id=${deviceId}`);
                    const status = await response.json();
                    updatePatreonUI(status);
                    return status;
                } catch (e) {
                    console.error("Morpheus: Patreon status check error", e);
                    return { authenticated: false };
                }
            };

            // Track OAuth completion to prevent duplicate status checks
            let oauthCompleted = false;
            let activePollTimer = null;
            
            // Listen for OAuth completion message from popup
            window.addEventListener("message", (event) => {
                if (event.data && (event.data.type === "patreon_oauth_complete" || event.data.type === "patreon-auth-complete")) {
                    oauthCompleted = true;
                    if (activePollTimer) {
                        clearInterval(activePollTimer);
                        activePollTimer = null;
                    }
                    if (event.data.success) {
                        checkPatreonStatus().then(() => {
                            // Refresh gallery after successful authentication
                            renderTalents();
                        });
                    } else {
                        patreonMembershipStatus.style.display = "block";
                        patreonMembershipStatus.textContent = event.data.error || "OAuth failed";
                        patreonMembershipStatus.style.color = "#ff6666";
                    }
                }
            });
            
            patreonConnectBtn.addEventListener("click", async () => {
                oauthCompleted = false;
                const deviceId = await MorpheusGalleryNode.getDeviceId();
                const authUrl = `${SUPABASE_FUNCTIONS_URL}/patreon-authorize?device_id=${deviceId}`;
                const popup = window.open(authUrl, "_blank", "width=600,height=700");
                
                // Fallback: poll for popup close in case postMessage doesn't work
                activePollTimer = setInterval(() => {
                    if (popup && popup.closed) {
                        clearInterval(activePollTimer);
                        activePollTimer = null;
                        // Only refresh if postMessage hasn't already handled it
                        if (!oauthCompleted) {
                            setTimeout(() => {
                                checkPatreonStatus().then(() => {
                                    // Refresh gallery after popup closes
                                    renderTalents();
                                });
                            }, 500);
                        }
                    }
                }, 500);
                
                // Clear poll after 5 minutes to prevent memory leak
                setTimeout(() => {
                    if (activePollTimer) {
                        clearInterval(activePollTimer);
                        activePollTimer = null;
                    }
                }, 300000);
            });

            patreonCheckBtn.addEventListener("click", async () => {
                patreonMembershipStatus.style.display = "block";
                patreonMembershipStatus.textContent = "Checking membership...";
                patreonMembershipStatus.style.color = "#888";
                
                try {
                    const deviceId = await MorpheusGalleryNode.getDeviceId();
                    const response = await fetch(`${SUPABASE_FUNCTIONS_URL}/patreon-membership?device_id=${deviceId}`);
                    const data = await response.json();
                    
                    if (data.is_patron) {
                        let statusMsg = "Active Patron";
                        if (data.cached) statusMsg += " (cached)";
                        if (data.offline_mode) statusMsg += " - offline mode";
                        if (data.needs_reauth) {
                            statusMsg += " - please reconnect soon";
                            patreonMembershipStatus.style.color = "#ffaa00";
                            // Show reconnect button
                            patreonConnectBtn.style.display = "inline-block";
                            patreonConnectBtn.textContent = "Reconnect";
                            patreonConnectBtn.style.background = "#ffaa00";
                        } else {
                            patreonMembershipStatus.style.color = "#00ff88";
                        }
                        patreonMembershipStatus.textContent = statusMsg;
                    } else if (data.needs_reauth) {
                        patreonMembershipStatus.textContent = "Token expired - please reconnect with Patreon";
                        patreonMembershipStatus.style.color = "#ffaa00";
                        // Update UI to show reconnect button
                        checkPatreonStatus();
                    } else {
                        patreonMembershipStatus.textContent = data.error || "Not an active patron";
                        patreonMembershipStatus.style.color = "#ff6666";
                    }
                } catch (e) {
                    patreonMembershipStatus.textContent = "Error checking membership";
                    patreonMembershipStatus.style.color = "#ff6666";
                }
            });

            patreonLogoutBtn.addEventListener("click", async () => {
                try {
                    const deviceId = await MorpheusGalleryNode.getDeviceId();
                    await fetch(`${SUPABASE_FUNCTIONS_URL}/patreon-logout?device_id=${deviceId}`);
                    updatePatreonUI({ authenticated: false });
                } catch (e) {
                    console.error("Morpheus: Patreon logout error", e);
                }
            });

            checkPatreonStatus();

            // State management
            const updateSelection = (talentId) => {
                this.selectedTalentId = talentId;
                this.properties.selected_talent_id = talentId;
                
                const widget = this.widgets.find(w => w.name === "selected_talent_id");
                if (widget) {
                    widget.value = talentId;
                }

                // Save state and trigger node re-execution
                MorpheusGalleryNode.setUiState(this.id, this.properties.morpheus_gallery_id, {
                    selected_talent_id: talentId,
                    filters: this.filters
                });
                
                // Mark node dirty to trigger re-execution
                this.setDirtyCanvas(true, true);
            };

            const updatePreview = (talent) => {
                if (talent) {
                    previewImage.src = talent.thumbnail_url || "";
                    previewImage.style.display = talent.thumbnail_url ? "block" : "none";
                    previewName.textContent = talent.name;
                    
                    // Show tags and description
                    const tags = talent.tags ? talent.tags.join(", ") : "";
                    const description = talent.description || "";
                    
                    if (tags && description) {
                        previewTags.textContent = tags + " • " + description;
                    } else if (tags) {
                        previewTags.textContent = tags;
                    } else if (description) {
                        previewTags.textContent = description;
                    } else {
                        previewTags.textContent = "";
                    }
                } else {
                    previewImage.style.display = "none";
                    previewName.textContent = "Loading...";
                    previewTags.textContent = "";
                }
            };

            const renderTalents = async () => {
                if (MorpheusGalleryNode.isLoading) return;

                // Use fixed paths
                const catalogPath = "catalog/catalog.json";
                const imagesFolder = "catalog/images";

                const data = await MorpheusGalleryNode.getTalents(
                    catalogPath, 
                    imagesFolder, 
                    this.filters, 
                    MorpheusGalleryNode.currentPage
                );
                
                galleryEl.innerHTML = "";
                
                // Check if user is not authenticated - show Connect Patreon overlay
                if (data.authenticated === false || data.show_cta === true) {
                    const isPatronButLowTier = data.is_patron === true && data.tier_met === false;
                    
                    const authOverlay = document.createElement("div");
                    authOverlay.className = "morpheus-auth-overlay";
                    authOverlay.innerHTML = isPatronButLowTier ? `
                        <div class="auth-overlay-content">
                            <div class="auth-overlay-icon">⭐</div>
                            <div class="auth-overlay-title">Upgrade Required</div>
                            <div class="auth-overlay-text">This content is exclusive to R&D Insider (15€) and Lab Access (100€) tiers.<br>Upgrade your membership to unlock the talent catalog.</div>
                            <button class="auth-overlay-btn" onclick="window.open('https://www.patreon.com/morpheus_tutorials', '_blank')">View Tiers on Patreon</button>
                        </div>
                    ` : `
                        <div class="auth-overlay-content">
                            <div class="auth-overlay-icon">🔒</div>
                            <div class="auth-overlay-title">Exclusive Content</div>
                            <div class="auth-overlay-text">Connect with Patreon to access the talent catalog.<br>Requires R&D Insider (15€) or Lab Access (100€) tier.</div>
                            <button class="auth-overlay-btn">Connect Patreon</button>
                        </div>
                    `;
                    authOverlay.style.cssText = `
                        display: flex; align-items: center; justify-content: center;
                        width: 100%; height: 100%; min-height: 300px;
                        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
                        border-radius: 8px; text-align: center;
                    `;
                    const overlayContent = authOverlay.querySelector(".auth-overlay-content");
                    overlayContent.style.cssText = `padding: 40px;`;
                    authOverlay.querySelector(".auth-overlay-icon").style.cssText = `font-size: 48px; margin-bottom: 16px;`;
                    authOverlay.querySelector(".auth-overlay-title").style.cssText = `font-size: 20px; font-weight: bold; color: #fff; margin-bottom: 8px;`;
                    authOverlay.querySelector(".auth-overlay-text").style.cssText = `font-size: 14px; color: #aaa; margin-bottom: 20px;`;
                    const authBtn = authOverlay.querySelector(".auth-overlay-btn");
                    authBtn.style.cssText = `
                        background: #f96854; color: #fff; border: none;
                        padding: 12px 24px; border-radius: 6px;
                        cursor: pointer; font-size: 14px; font-weight: bold;
                    `;
                    authBtn.addEventListener("click", async () => {
                        const deviceId = await MorpheusGalleryNode.getDeviceId();
                        const authUrl = `${SUPABASE_FUNCTIONS_URL}/patreon-authorize?device_id=${deviceId}`;
                        window.open(authUrl, "_blank", "width=600,height=700");
                    });
                    galleryEl.appendChild(authOverlay);
                    return;
                }
                
                // Add upload card only on page 1
                if (MorpheusGalleryNode.currentPage === 1) {
                    const uploadCard = document.createElement("div");
                    uploadCard.className = "morpheus-talent-card morpheus-upload-card";
                    uploadCard.innerHTML = `
                        <div class="upload-content">
                            <div class="upload-icon">📸</div>
                            <div class="upload-text">Upload Talent</div>
                            <div class="upload-hint">(jpg, png)</div>
                        </div>
                        <input type="file" class="upload-input" accept=".jpg,.jpeg,.png" style="display: none;">
                    `;
                    
                    // Upload click handler
                    uploadCard.addEventListener("click", () => {
                        const fileInput = uploadCard.querySelector(".upload-input");
                        fileInput.click();
                    });
                    
                    // File selection handler
                    const fileInput = uploadCard.querySelector(".upload-input");
                    fileInput.addEventListener("change", handleFileUpload);
                    
                    galleryEl.appendChild(uploadCard);
                }
                
                if (data.talents.length === 0) {
                    const noTalentsMsg = document.createElement('div');
                    noTalentsMsg.className = 'morpheus-loading';
                    noTalentsMsg.textContent = 'No talents found';
                    galleryEl.appendChild(noTalentsMsg);
                    return;
                }

                // Display all talents returned by server (server handles pagination correctly)
                data.talents.forEach(talent => {
                    const card = document.createElement("div");
                    card.className = "morpheus-talent-card";
                    if (talent.id === this.selectedTalentId) {
                        card.classList.add("selected");
                    }
                    
                    card.innerHTML = `
                        <div class="morpheus-selection-badge">✓</div>
                        <div class="talent-actions">
                            <button class="action-btn edit" data-talent-id="${talent.id}" title="Edit Talent">✏️</button>
                            <button class="action-btn delete" data-talent-id="${talent.id}" title="Delete Talent">🗑️</button>
                        </div>
                        <div class="morpheus-media-container">
                            <span class="morpheus-favorite-star ${talent.is_favorite ? 'active' : ''}" data-talent-id="${talent.id}">★</span>
                            <img src="${talent.thumbnail_url || ''}" alt="${talent.name}" onerror="this.style.display='none';" class="talent-image">
                        </div>
                        <div class="morpheus-talent-info">
                            <div class="morpheus-talent-name">${talent.name}</div>
                            <div class="morpheus-talent-tags">
                                ${(talent.tags || []).map(tag => `<span class="tag">${tag}</span>`).join('')}
                            </div>
                        </div>
                    `;
                    
                    // Star click handler
                    const star = card.querySelector(".morpheus-favorite-star");
                    star.addEventListener("click", async (e) => {
                        e.stopPropagation();
                        try {
                            const response = await api.fetchApi("/morpheus/favorite", {
                                method: "POST",
                                headers: { "Content-Type": "application/json" },
                                body: JSON.stringify({ talent_id: talent.id })
                            });
                            const result = await response.json();
                            if (result.status === "success") {
                                talent.is_favorite = result.is_favorite;
                                star.classList.toggle("active", talent.is_favorite);
                            } else {
                                console.error("Morpheus: API error:", result.error || "Unknown error");
                            }
                        } catch (error) {
                            console.error("Morpheus: Failed to toggle favorite", error);
                        }
                    });
                    
                    // Edit button handler
                    const editBtn = card.querySelector(".action-btn.edit");
                    editBtn.addEventListener("click", async (e) => {
                        e.stopPropagation();
                        try {
                            const response = await api.fetchApi(`/morpheus/talent/${talent.id}`);
                            const talentData = await response.json();
                            if (talentData.status === 'success') {
                                showMetadataForm(null, null, talentData.talent);
                            } else {
                                alert('Failed to load talent data: ' + talentData.error);
                            }
                        } catch (error) {
                            console.error('Error loading talent for edit:', error);
                            alert('Failed to load talent data');
                        }
                    });
                    
                    // Delete button handler
                    const deleteBtn = card.querySelector(".action-btn.delete");
                    deleteBtn.addEventListener("click", async (e) => {
                        e.stopPropagation();
                        if (confirm(`Are you sure you want to delete "${talent.name}"? This action cannot be undone.`)) {
                            try {
                                const response = await api.fetchApi("/morpheus/delete_talent", {
                                    method: "POST",
                                    headers: { "Content-Type": "application/json" },
                                    body: JSON.stringify({ talent_id: talent.id })
                                });
                                const result = await response.json();
                                if (result.status === "success") {
                                    // Refresh the gallery
                                    renderTalents();
                                } else {
                                    alert('Failed to delete talent: ' + result.error);
                                }
                            } catch (error) {
                                console.error('Error deleting talent:', error);
                                alert('Failed to delete talent');
                            }
                        }
                    });
                    
                    // Image single click handler - selection only
                    const img = card.querySelector(".talent-image");
                    img.addEventListener("click", (e) => {
                        e.stopPropagation();
                        
                        // Select the talent
                        galleryEl.querySelectorAll(".morpheus-talent-card").forEach(c => c.classList.remove("selected"));
                        card.classList.add("selected");
                        
                        updateSelection(talent.id);
                        updatePreview(talent);
                    });
                    
                    // Image double click handler - zoom
                    img.addEventListener("dblclick", (e) => {
                        e.stopPropagation();
                        
                        // Show zoom starting from this specific talent
                        showImageZoom(talent, data.talents);
                    });
                    
                    // Card selection handler
                    card.addEventListener("click", () => {
                        galleryEl.querySelectorAll(".morpheus-talent-card").forEach(c => c.classList.remove("selected"));
                        card.classList.add("selected");
                        
                        updateSelection(talent.id);
                        updatePreview(talent);
                    });
                    
                    galleryEl.appendChild(card);
                });

                // Update pagination
                pageInfo.textContent = `Page ${data.current_page} of ${data.total_pages}`;
                prevPageBtn.disabled = data.current_page <= 1;
                nextPageBtn.disabled = data.current_page >= data.total_pages;
                
                // Update preview for selected talent
                if (this.selectedTalentId) {
                    const selectedTalent = data.talents.find(t => t.id === this.selectedTalentId);
                    if (selectedTalent) {
                        updatePreview(selectedTalent);
                    }
                }
            };

            // Advanced image zoom with navigation
            let currentZoomIndex = 0;
            let zoomTalents = [];
            
            const showImageZoom = (selectedTalent, allTalents) => {
                // Set talents array for navigation
                zoomTalents = allTalents;
                
                // Find current talent index based on talent ID
                currentZoomIndex = zoomTalents.findIndex(t => t.id === selectedTalent.id);
                if (currentZoomIndex === -1) currentZoomIndex = 0;
                
                createZoomOverlay();
            };
            
            const createZoomOverlay = () => {
                // Remove existing overlay if any
                const existing = document.querySelector('.morpheus-fullscreen-zoom');
                if (existing) existing.remove();
                
                const overlay = document.createElement("div");
                overlay.className = "morpheus-fullscreen-zoom";
                
                const talent = zoomTalents[currentZoomIndex];
                overlay.innerHTML = `
                    <div class="zoom-nav prev" onclick="navigateZoom(-1)">‹</div>
                    <img class="zoom-image" src="${talent.full_image_url || talent.thumbnail_url}" alt="${talent.name}" onerror="if(this.src !== '${talent.thumbnail_url}') this.src='${talent.thumbnail_url}';">
                    <div class="zoom-nav next" onclick="navigateZoom(1)">›</div>
                    <div class="zoom-close" onclick="closeZoom()">×</div>
                    <div class="zoom-title">${talent.name}</div>
                `;
                
                document.body.appendChild(overlay);
                
                // Trigger animation
                requestAnimationFrame(() => {
                    overlay.classList.add('active');
                });
                
                // Global event listeners
                document.addEventListener('keydown', handleZoomKeydown);
            };
            
            window.navigateZoom = (direction) => {
                currentZoomIndex += direction;
                if (currentZoomIndex < 0) currentZoomIndex = zoomTalents.length - 1;
                if (currentZoomIndex >= zoomTalents.length) currentZoomIndex = 0;
                
                const img = document.querySelector('.morpheus-fullscreen-zoom .zoom-image');
                const title = document.querySelector('.morpheus-fullscreen-zoom .zoom-title');
                const talent = zoomTalents[currentZoomIndex];
                
                if (img && title && talent) {
                    img.src = talent.full_image_url || talent.thumbnail_url;
                    img.alt = talent.name;
                    img.onerror = function() {
                        if (this.src !== talent.thumbnail_url) {
                            this.src = talent.thumbnail_url;
                        }
                    };
                    title.textContent = talent.name;
                }
            };
            
            window.closeZoom = () => {
                const overlay = document.querySelector('.morpheus-fullscreen-zoom');
                if (overlay) {
                    overlay.classList.remove('active');
                    setTimeout(() => {
                        overlay.remove();
                        document.removeEventListener('keydown', handleZoomKeydown);
                    }, 300);
                }
            };
            
            const handleZoomKeydown = (e) => {
                switch(e.key) {
                    case 'Escape':
                        closeZoom();
                        break;
                    case 'ArrowLeft':
                        navigateZoom(-1);
                        break;
                    case 'ArrowRight':
                        navigateZoom(1);
                        break;
                }
            };

            // File upload handler
            const handleFileUpload = async (event) => {
                const file = event.target.files[0];
                if (!file) return;

                // Validate file type
                if (!file.type.match(/image\/(jpeg|jpg|png)/)) {
                    alert('Please select a JPG or PNG image file.');
                    return;
                }

                // Show loading
                const uploadCard = event.target.closest('.morpheus-upload-card');
                const originalContent = uploadCard.innerHTML;
                uploadCard.innerHTML = '<div class="upload-content"><div class="upload-icon">⏳</div><div class="upload-text">Uploading...</div></div>';

                try {
                    // Upload file
                    const formData = new FormData();
                    formData.append('image', file);
                    
                    const response = await api.fetchApi('/morpheus/upload', {
                        method: 'POST',
                        body: formData
                    });

                    const result = await response.json();
                    
                    if (result.status === 'success') {
                        // Show metadata form
                        showMetadataForm(result.temp_filename, file.name);
                    } else {
                        throw new Error(result.error || 'Upload failed');
                    }
                } catch (error) {
                    console.error('Upload error:', error);
                    alert('Failed to upload image: ' + error.message);
                } finally {
                    // Restore upload card
                    uploadCard.innerHTML = originalContent;
                    
                    // Re-add event listeners
                    uploadCard.addEventListener("click", () => {
                        const fileInput = uploadCard.querySelector(".upload-input");
                        fileInput.click();
                    });
                    
                    const fileInput = uploadCard.querySelector(".upload-input");
                    fileInput.addEventListener("change", handleFileUpload);
                }
            };

            // Show metadata form modal
            const showMetadataForm = (tempFilename, originalName, editTalent = null) => {
                const modal = document.createElement('div');
                modal.className = 'morpheus-metadata-modal';
                modal.innerHTML = `
                    <div class="metadata-form-container">
                        <h3>${editTalent ? 'Edit Talent Metadata' : 'Add Talent Metadata'}</h3>
                        <form class="metadata-form">
                            <div class="form-row">
                                <label>Name:</label>
                                <input type="text" name="name" required placeholder="Enter talent name">
                            </div>
                            <div class="form-row">
                                <label>Gender:</label>
                                <select name="gender" required>
                                    <option value="">Select gender</option>
                                    <option value="male">Male</option>
                                    <option value="female">Female</option>
                                    <option value="non_binary">Non-binary</option>
                                    <option value="other">Other</option>
                                </select>
                            </div>
                            <div class="form-row">
                                <label>Age Group:</label>
                                <select name="age_group" required>
                                    <option value="">Select age group</option>
                                    <option value="child">Child</option>
                                    <option value="teen">Teen</option>
                                    <option value="young_adult">Young Adult</option>
                                    <option value="adult">Adult</option>
                                    <option value="mature">Mature</option>
                                    <option value="senior">Senior</option>
                                </select>
                            </div>
                            <div class="form-row">
                                <label>Ethnicity:</label>
                                <select name="ethnicity" required>
                                    <option value="">Select ethnicity</option>
                                    <option value="caucasian">Caucasian</option>
                                    <option value="african">African</option>
                                    <option value="asian">Asian</option>
                                    <option value="hispanic">Hispanic</option>
                                    <option value="mixed">Mixed</option>
                                    <option value="middle_eastern">Middle Eastern</option>
                                    <option value="other">Other</option>
                                </select>
                            </div>
                            <div class="form-row">
                                <label>Hair Color:</label>
                                <input type="text" name="hair_color" placeholder="e.g., brown, blonde, black">
                            </div>
                            <div class="form-row">
                                <label>Hair Style:</label>
                                <input type="text" name="hair_style" placeholder="e.g., long_wavy, short, curly">
                            </div>
                            <div class="form-row">
                                <label>Eye Color:</label>
                                <input type="text" name="eye_color" placeholder="e.g., brown, blue, green">
                            </div>
                            <div class="form-row">
                                <label>Tags (comma separated):</label>
                                <input type="text" name="tags" placeholder="brunette, fashion, commercial, professional">
                            </div>
                            <div class="form-row">
                                <label>Description:</label>
                                <textarea name="description" rows="3" placeholder="Brief description of the talent"></textarea>
                            </div>
                            <div class="form-buttons">
                                <button type="button" class="cancel-btn">Cancel</button>
                                <button type="submit" class="save-btn">${editTalent ? 'Update Talent' : 'Save Talent'}</button>
                            </div>
                        </form>
                    </div>
                `;

                // Add modal styles
                const style = document.createElement('style');
                style.textContent = `
                    .morpheus-metadata-modal {
                        position: fixed; top: 0; left: 0; right: 0; bottom: 0;
                        background: rgba(0,0,0,0.8); display: flex; align-items: center;
                        justify-content: center; z-index: 25000;
                    }
                    .metadata-form-container {
                        background: #2a2a2a; border-radius: 8px; padding: 24px;
                        width: 90%; max-width: 500px; max-height: 80vh; overflow-y: auto;
                        border: 1px solid #555;
                    }
                    .metadata-form-container h3 {
                        margin: 0 0 20px 0; color: #fff; text-align: center;
                    }
                    .metadata-form .form-row {
                        margin-bottom: 15px;
                    }
                    .metadata-form label {
                        display: block; margin-bottom: 5px; color: #ccc; font-size: 14px;
                    }
                    .metadata-form input, .metadata-form select, .metadata-form textarea {
                        width: 100%; padding: 8px; border: 1px solid #555;
                        border-radius: 4px; background: #1a1a1a; color: #fff;
                        font-size: 14px; box-sizing: border-box;
                    }
                    .metadata-form input:focus, .metadata-form select:focus, .metadata-form textarea:focus {
                        outline: none; border-color: #00FFC9;
                    }
                    .form-buttons {
                        display: flex; gap: 10px; justify-content: flex-end; margin-top: 20px;
                    }
                    .form-buttons button {
                        padding: 10px 20px; border: none; border-radius: 4px;
                        cursor: pointer; font-size: 14px; font-weight: bold;
                    }
                    .cancel-btn {
                        background: #666; color: #fff;
                    }
                    .cancel-btn:hover {
                        background: #777;
                    }
                    .save-btn {
                        background: #00FFC9; color: #000;
                    }
                    .save-btn:hover {
                        background: #00DDaa;
                    }
                `;
                document.head.appendChild(style);

                document.body.appendChild(modal);
                
                // Pre-fill form if editing
                if (editTalent) {
                    const form = modal.querySelector('.metadata-form');
                    form.querySelector('[name="name"]').value = editTalent.name || '';
                    form.querySelector('[name="gender"]').value = editTalent.gender || '';
                    form.querySelector('[name="age_group"]').value = editTalent.age_group || '';
                    form.querySelector('[name="ethnicity"]').value = editTalent.ethnicity || '';
                    form.querySelector('[name="hair_color"]').value = editTalent.hair_color || '';
                    form.querySelector('[name="hair_style"]').value = editTalent.hair_style || '';
                    form.querySelector('[name="eye_color"]').value = editTalent.eye_color || '';
                    form.querySelector('[name="tags"]').value = (editTalent.tags || []).join(', ');
                    form.querySelector('[name="description"]').value = editTalent.description || '';
                }

                // Handle form submission
                const form = modal.querySelector('.metadata-form');
                form.addEventListener('submit', async (e) => {
                    e.preventDefault();
                    
                    const formData = new FormData(form);
                    let metadata, endpoint;
                    
                    if (editTalent) {
                        // Edit mode
                        metadata = {
                            talent_id: editTalent.id,
                            name: formData.get('name'),
                            gender: formData.get('gender'),
                            age_group: formData.get('age_group'),
                            ethnicity: formData.get('ethnicity'),
                            hair_color: formData.get('hair_color'),
                            hair_style: formData.get('hair_style'),
                            eye_color: formData.get('eye_color'),
                            tags: formData.get('tags').split(',').map(tag => tag.trim()).filter(tag => tag),
                            description: formData.get('description')
                        };
                        endpoint = '/morpheus/update_talent';
                    } else {
                        // Add mode
                        metadata = {
                            temp_filename: tempFilename,
                            original_name: originalName,
                            name: formData.get('name'),
                            gender: formData.get('gender'),
                            age_group: formData.get('age_group'),
                            ethnicity: formData.get('ethnicity'),
                            hair_color: formData.get('hair_color'),
                            hair_style: formData.get('hair_style'),
                            eye_color: formData.get('eye_color'),
                            tags: formData.get('tags').split(',').map(tag => tag.trim()).filter(tag => tag),
                            description: formData.get('description')
                        };
                        endpoint = '/morpheus/save_talent';
                    }

                    try {
                        const response = await api.fetchApi(endpoint, {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify(metadata)
                        });

                        const result = await response.json();
                        
                        if (result.status === 'success') {
                            // Close modal and refresh gallery
                            document.body.removeChild(modal);
                            document.head.removeChild(style);
                            renderTalents();
                        } else {
                            throw new Error(result.error || 'Failed to save talent');
                        }
                    } catch (error) {
                        console.error('Save error:', error);
                        alert('Failed to save talent: ' + error.message);
                    }
                });

                // Handle cancel
                modal.querySelector('.cancel-btn').addEventListener('click', () => {
                    document.body.removeChild(modal);
                    document.head.removeChild(style);
                });
            };

            const applyFilters = () => {
                this.filters = {
                    name: nameFilter.value,
                    tags: tagsFilter.value,
                    logic: tagLogicBtn.textContent,
                    gender: genderFilter.value,
                    age_group: ageFilter.value,
                    ethnicity: ethnicityFilter.value,
                    favorites_only: favoritesFilter.checked
                };
                MorpheusGalleryNode.currentPage = 1;
                renderTalents();
            };

            // Event listeners

            tagLogicBtn.addEventListener("click", () => {
                tagLogicBtn.textContent = tagLogicBtn.textContent === "OR" ? "AND" : "OR";
                applyFilters();
            });

            nameFilter.addEventListener("input", applyFilters);
            tagsFilter.addEventListener("input", applyFilters);
            favoritesFilter.addEventListener("change", applyFilters);
            genderFilter.addEventListener("change", applyFilters);
            ageFilter.addEventListener("change", applyFilters);
            ethnicityFilter.addEventListener("change", applyFilters);

            prevPageBtn.addEventListener("click", () => {
                if (MorpheusGalleryNode.currentPage > 1) {
                    MorpheusGalleryNode.currentPage--;
                    renderTalents();
                }
            });

            nextPageBtn.addEventListener("click", () => {
                if (MorpheusGalleryNode.currentPage < MorpheusGalleryNode.totalPages) {
                    MorpheusGalleryNode.currentPage++;
                    renderTalents();
                }
            });
            
            refreshBtn.addEventListener("click", () => {
                // Reset to first page and refresh
                MorpheusGalleryNode.currentPage = 1;
                renderTalents();
            });

            // Initialize gallery with default size
            this.size[1] = 600;
            
            // Auto-load talents on initialization
            this.autoLoadTalents = async () => {
                try {
                    await this.initializeNode();
                    await renderTalents();
                } catch (error) {
                    console.error("Morpheus: Error auto-loading talents:", error);
                }
            };

            // Initialize node
            this.initializeNode = async () => {
                const state = await MorpheusGalleryNode.getUiState(this.id, this.properties.morpheus_gallery_id);
                
                this.selectedTalentId = state.selected_talent_id || "";
                this.properties.selected_talent_id = this.selectedTalentId;
                
                // Restore license credentials from state or properties
                this.licenseKey = state.license_key || this.properties.license_key || "";
                this.licenseEmail = state.license_email || this.properties.license_email || "";
                this.properties.license_key = this.licenseKey;
                this.properties.license_email = this.licenseEmail;
                licenseKeyInput.value = this.licenseKey;
                licenseEmailInput.value = this.licenseEmail;
                
                this.filters = state.filters || {
                    name: "",
                    tags: "",
                    logic: "OR",
                    gender: "",
                    age_group: "",
                    ethnicity: "",
                    favorites_only: false
                };

                // Update UI controls
                nameFilter.value = this.filters.name;
                tagsFilter.value = this.filters.tags;
                tagLogicBtn.textContent = this.filters.logic;
                favoritesFilter.checked = this.filters.favorites_only;
                genderFilter.value = this.filters.gender;
                ageFilter.value = this.filters.age_group;
                ethnicityFilter.value = this.filters.ethnicity;

                // Update selection widget
                const widget = this.widgets.find(w => w.name === "selected_talent_id");
                if (widget) {
                    widget.value = this.selectedTalentId;
                }
            };

            setTimeout(() => this.autoLoadTalents(), 100);

            return result;
        };
    }
};

app.registerExtension({
    name: "Morpheus.ModelManagement.GalleryUI",
    async beforeRegisterNodeDef(nodeType, nodeData) {
        if (nodeData.name === "MorpheusModelManagement") {
            MorpheusGalleryNode.setup(nodeType, nodeData);
        }
    },
});