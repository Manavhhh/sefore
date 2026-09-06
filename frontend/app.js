/**
 * Sefore: Satellite SAR Oil Spill Detection & AIS Vessel Attribution Engine
 * Smart India Hackathon 2026 - PS ID: SIH26143
 */

document.addEventListener("DOMContentLoaded", () => {
  // DOM Elements - Ingestion & Detection
  const dropZone = document.getElementById("drop-zone");
  const fileInput = document.getElementById("file-input");
  const sampleSelect = document.getElementById("sample-select");
  const btnRunSample = document.getElementById("btn-run-sample");
  const btnFitSpill = document.getElementById("btn-fit-spill");
  const btnFitAll = document.getElementById("btn-fit-all");
  const btnDownloadGeoJSON = document.getElementById("btn-download-geojson");
  const btnDownloadConsolidated = document.getElementById("btn-download-consolidated");
  const btnOpenModalNav = document.getElementById("btn-open-modal-nav");

  // Metric displays
  const metricRegions = document.getElementById("metric-regions");
  const metricConfidence = document.getElementById("metric-confidence");
  const metricArea = document.getElementById("metric-area");
  const metricCoords = document.getElementById("metric-coords");
  const mapSubtitle = document.getElementById("map-subtitle");

  // Prime Suspect Vessel HUD Elements
  const vesselCountBadge = document.getElementById("vessel-count");
  const primeRiskBadge = document.getElementById("prime-risk-badge");
  const primeVesselName = document.getElementById("prime-vessel-name");
  const primeVesselFlag = document.getElementById("prime-vessel-flag");
  const primeVesselType = document.getElementById("prime-vessel-type");
  const primeVesselMmsi = document.getElementById("prime-vessel-mmsi");
  const primeVesselSpeed = document.getElementById("prime-vessel-speed");
  const primeCpaDist = document.getElementById("prime-cpa-dist");
  const primeTimeDelta = document.getElementById("prime-time-delta");
  const primeSuspectScore = document.getElementById("prime-suspect-score");
  const primeScoreBar = document.getElementById("prime-score-bar");
  const primeDirectiveText = document.getElementById("prime-directive-text");
  const vesselLeaderboardList = document.getElementById("vessel-leaderboard-list");

  // Layer Toggles
  const toggleLayerSpill = document.getElementById("toggle-layer-spill");
  const toggleLayerVessels = document.getElementById("toggle-layer-vessels");
  const toggleLayerCpa = document.getElementById("toggle-layer-cpa");

  // Imagery Panels & JSON Viewer
  const imgOverlay = document.getElementById("img-overlay");
  const imgMask = document.getElementById("img-mask");
  const imgSar = document.getElementById("img-sar");
  const jsonCodeBlock = document.getElementById("json-code-block");
  const btnCopyJson = document.getElementById("btn-copy-json");
  const btnDownloadTabJson = document.getElementById("btn-download-tab-json");

  // Modal Elements
  const analyticsModal = document.getElementById("analytics-modal");
  const btnCloseModal = document.getElementById("btn-close-modal");
  const modalEnforcementText = document.getElementById("modal-enforcement-text");
  const modalJsonContent = document.getElementById("modal-json-content");
  const btnModalCopy = document.getElementById("btn-modal-copy");
  const btnModalDownload = document.getElementById("btn-modal-download");

  // Tabs
  const tabBtns = document.querySelectorAll(".tab-btn");
  const tabPanels = document.querySelectorAll(".tab-panel");

  // Application State
  let currentResults = null;
  let currentConsolidatedJSON = null;
  let staticManifest = null;
  let currentSpillLayer = null;

  // Initialize Leaflet Map
  const map = L.map("leaflet-map", {
    center: [55.242, 4.052],
    zoom: 8,
    attributionControl: true,
  });

  const osmLayer = L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    maxZoom: 19,
  });

  const esriOcean = L.tileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/Ocean/World_Ocean_Base/MapServer/tile/{z}/{y}/{x}", {
    attribution: 'Tiles &copy; Esri &mdash; Sources: GEBCO, NOAA, CHS, OSU, UNH, CSUMB',
    maxZoom: 13,
  });

  const esriSat = L.tileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}", {
    attribution: 'Tiles &copy; Esri &mdash; Source: Esri, i-cubed, USDA, USGS, AEX, GeoEye',
    maxZoom: 18,
  });

  osmLayer.addTo(map);

  L.control.layers({
    "OpenStreetMap": osmLayer,
    "Esri Ocean Basemap": esriOcean,
    "Satellite Imagery": esriSat,
  }, null, { position: "topright" }).addTo(map);

  // Dedicated Layer Groups
  const spillLayerGroup = L.layerGroup().addTo(map);
  const vesselLayerGroup = L.layerGroup().addTo(map);
  const cpaLayerGroup = L.layerGroup().addTo(map);

  // Layer toggle listeners
  if (toggleLayerSpill) {
    toggleLayerSpill.addEventListener("change", (e) => {
      if (e.target.checked) map.addLayer(spillLayerGroup);
      else map.removeLayer(spillLayerGroup);
    });
  }

  if (toggleLayerVessels) {
    toggleLayerVessels.addEventListener("change", (e) => {
      if (e.target.checked) map.addLayer(vesselLayerGroup);
      else map.removeLayer(vesselLayerGroup);
    });
  }

  if (toggleLayerCpa) {
    toggleLayerCpa.addEventListener("change", (e) => {
      if (e.target.checked) map.addLayer(cpaLayerGroup);
      else map.removeLayer(cpaLayerGroup);
    });
  }

  // Tab switching
  tabBtns.forEach((btn) => {
    btn.addEventListener("click", () => {
      tabBtns.forEach((b) => b.classList.remove("active"));
      tabPanels.forEach((p) => p.classList.remove("active"));

      btn.classList.add("active");
      const targetId = btn.getAttribute("data-target");
      const targetPanel = document.getElementById(targetId);
      if (targetPanel) {
        targetPanel.classList.add("active");
      }
    });
  });

  // Modal open/close
  function openAnalyticsModal() {
    if (!currentConsolidatedJSON) return;
    analyticsModal.classList.add("open");
  }

  function closeAnalyticsModal() {
    analyticsModal.classList.remove("open");
  }

  if (btnOpenModalNav) btnOpenModalNav.addEventListener("click", openAnalyticsModal);
  if (btnCloseModal) btnCloseModal.addEventListener("click", closeAnalyticsModal);
  analyticsModal.addEventListener("click", (e) => {
    if (e.target === analyticsModal) closeAnalyticsModal();
  });

  // Copy JSON utility
  async function copyJSONToClipboard(buttonEl) {
    if (!currentConsolidatedJSON) return;
    const jsonStr = JSON.stringify(currentConsolidatedJSON, null, 2);
    try {
      await navigator.clipboard.writeText(jsonStr);
      const originalText = buttonEl.textContent;
      buttonEl.textContent = "Copied!";
      buttonEl.style.color = "#10b981";
      setTimeout(() => {
        buttonEl.textContent = originalText;
        buttonEl.style.color = "";
      }, 2000);
    } catch (err) {
      console.error("Clipboard copy failed:", err);
    }
  }

  if (btnCopyJson) btnCopyJson.addEventListener("click", () => copyJSONToClipboard(btnCopyJson));
  if (btnModalCopy) btnModalCopy.addEventListener("click", () => copyJSONToClipboard(btnModalCopy));

  // Trigger download of final_spill_data.json
  function downloadConsolidatedJSON() {
    if (!currentConsolidatedJSON) return;
    const jsonStr = JSON.stringify(currentConsolidatedJSON, null, 2);
    const blob = new Blob([jsonStr], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "final_spill_data.json";
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }

  if (btnDownloadConsolidated) btnDownloadConsolidated.addEventListener("click", downloadConsolidatedJSON);
  if (btnDownloadTabJson) btnDownloadTabJson.addEventListener("click", downloadConsolidatedJSON);
  if (btnModalDownload) btnModalDownload.addEventListener("click", downloadConsolidatedJSON);

  // Download Spill GeoJSON
  if (btnDownloadGeoJSON) {
    btnDownloadGeoJSON.addEventListener("click", () => {
      const selected = sampleSelect.value || "00000.tif";
      const sampleId = selected.replace(".tif", "").replace(".tiff", "");
      window.location.href = `samples/${sampleId}/spill.geojson`;
    });
  }

  // Fit bounds actions
  if (btnFitSpill) {
    btnFitSpill.addEventListener("click", () => {
      if (currentSpillLayer && currentSpillLayer.getBounds && currentSpillLayer.getBounds().isValid()) {
        map.fitBounds(currentSpillLayer.getBounds(), { padding: [50, 50], maxZoom: 13 });
      }
    });
  }

  if (btnFitAll) {
    btnFitAll.addEventListener("click", () => {
      const allBounds = L.latLngBounds([]);
      [spillLayerGroup, vesselLayerGroup].forEach((group) => {
        group.eachLayer((layer) => {
          if (layer.getBounds && layer.getBounds().isValid()) {
            allBounds.extend(layer.getBounds());
          } else if (layer.getLatLng) {
            allBounds.extend(layer.getLatLng());
          }
        });
      });
      if (allBounds.isValid()) {
        map.fitBounds(allBounds, { padding: [40, 40] });
      }
    });
  }

  // Fallback Predefined Scenes (always available instantly)
  const defaultScenes = [
    { name: "00000.tif", id: "00000", count: 16, area: "1.21", prime: "NORDIC TITAN" },
    { name: "00002.tif", id: "00002", count: 68, area: "3.62", prime: "NORDIC TITAN" },
    { name: "00004.tif", id: "00004", count: 13, area: "3.42", prime: "NORDIC TITAN" },
    { name: "00006.tif", id: "00006", count: 6, area: "4.24", prime: "NORDIC TITAN" },
    { name: "00007.tif", id: "00007", count: 3, area: "5.09", prime: "NORDIC TITAN" },
    { name: "00008.tif", id: "00008", count: 1, area: "6.62", prime: "NORDIC TITAN" },
  ];

  function populateDropdownWithDefaultScenes() {
    sampleSelect.innerHTML = "";
    defaultScenes.forEach((s) => {
      const opt = document.createElement("option");
      opt.value = s.name;
      opt.textContent = `${s.name} (${s.count} slicks, ${s.area} km² - Suspect: ${s.prime})`;
      sampleSelect.appendChild(opt);
    });
  }

  // Load Scene Data (fetches final_spill_data.json and renders oil spills immediately)
  async function loadScene(sceneName) {
    if (!sceneName) sceneName = "00000.tif";
    const sampleId = sceneName.replace(".tif", "").replace(".tiff", "");

    btnRunSample.disabled = true;
    btnRunSample.textContent = "Loading...";

    const statusPill = document.getElementById("system-status");
    if (statusPill) {
      statusPill.innerHTML = '<span class="status-dot"></span> Correlating ' + sceneName;
    }

    try {
      // 1. Fetch final_spill_data.json for this scene
      const finalJsonUrl = `samples/${sampleId}/final_spill_data.json`;
      const resp = await fetch(finalJsonUrl);
      
      if (resp.ok) {
        const fullData = await resp.json();
        renderSceneFromConsolidatedData(sceneName, sampleId, fullData);
        return;
      }
    } catch (err) {
      console.warn("Could not load static final_spill_data.json directly, trying API fallback:", err);
    }

    // 2. Local live API fallback
    try {
      const resp = await fetch(`/detect-sample/${encodeURIComponent(sceneName)}`);
      if (resp.ok) {
        const ct = resp.headers.get("content-type") || "";
        if (ct.includes("application/json")) {
          const results = await resp.json();
          renderDetectionResults(results);
          return;
        }
      }
    } catch (apiErr) {
      console.error("API error:", apiErr);
    } finally {
      btnRunSample.disabled = false;
      btnRunSample.textContent = "Analyze";
    }
  }

  // Renders complete scene from final_spill_data.json (ultra-fast, client-side)
  function renderSceneFromConsolidatedData(sceneName, sampleId, data) {
    console.log("Rendering scene from final_spill_data.json:", sceneName, data);
    currentConsolidatedJSON = data;

    const sSum = data.spill_detection_summary || {};
    const vAn = data.vessel_identification_analytics || {};
    const prime = vAn.prime_suspect_vessel;
    const rankedVessels = vAn.ranked_suspect_leaderboard || [];

    // Synthesize results object
    const results = {
      name: sceneName,
      detected_regions_count: sSum.detected_regions_count || 0,
      highest_confidence: sSum.highest_heuristic_confidence || 0,
      total_estimated_area_km2: sSum.total_estimated_area_km2 || 0,
      total_estimated_area_m2: sSum.total_estimated_area_m2 || 0,
      features: data.spill_features || [],
      vessel_analytics: {
        total_vessels_tracked: vAn.total_vessels_tracked || rankedVessels.length,
        primary_suspect: prime,
        ranked_suspects: rankedVessels,
        vessel_geojson: vAn.vessel_trajectories_geojson,
        cpa_vectors_geojson: vAn.cpa_vectors_geojson,
      },
      overlay_url: `samples/${sampleId}/overlay.png`,
      mask_url: `samples/${sampleId}/mask.png`,
      sar_url: `samples/${sampleId}/preprocessed.png`,
      consolidated_analytics: data,
    };

    renderDetectionResults(results, true);

    btnRunSample.disabled = false;
    btnRunSample.textContent = "Analyze";

    const statusPill = document.getElementById("system-status");
    if (statusPill) {
      statusPill.innerHTML = '<span class="status-dot"></span> Active &bull; ' + sceneName;
    }
  }

  // Render Full Pipeline & Vessel Attribution Results onto Map & HUD
  function renderDetectionResults(results, isStatic = false) {
    console.log("renderDetectionResults invoked:", results);
    currentResults = results;

    // 1. Update Detection Metrics
    metricRegions.textContent = results.detected_regions_count || 0;
    metricConfidence.textContent = results.highest_confidence ? `${(results.highest_confidence * 100).toFixed(1)}%` : "--";
    metricArea.textContent = `${results.total_estimated_area_km2 || 0} km²`;

    let centroidLat = null;
    let centroidLon = null;
    if (results.features && results.features.length > 0) {
      const p = results.features[0].properties;
      centroidLat = p.centroid_lat;
      centroidLon = p.centroid_lon;
      metricCoords.textContent = `${centroidLat.toFixed(4)}°N, ${centroidLon.toFixed(4)}°E`;
    } else {
      metricCoords.textContent = "None";
    }

    btnDownloadGeoJSON.disabled = !results.features || results.features.length === 0;

    // 2. Update Imagery Views
    if (isStatic) {
      imgOverlay.src = results.overlay_url;
      imgMask.src = results.mask_url;
      imgSar.src = results.sar_url;
    } else {
      const ts = new Date().getTime();
      imgOverlay.src = `/output/overlay.png?t=${ts}`;
      imgMask.src = `/output/mask.png?t=${ts}`;
      imgSar.src = `/output/preprocessed.png?t=${ts}`;
    }

    // Hide placeholder messages as images are loaded
    document.querySelectorAll(".placeholder-text").forEach((el) => {
      el.style.display = "none";
    });

    // 3. Extract Vessel Analytics & Consolidated Analytics
    const vAnalytics = results.vessel_analytics || {};
    const prime = vAnalytics.primary_suspect;
    const rankedVessels = vAnalytics.ranked_suspects || [];

    if (results.consolidated_analytics) {
      currentConsolidatedJSON = results.consolidated_analytics;
    }

    // Enable JSON Actions
    btnDownloadConsolidated.disabled = false;
    btnOpenModalNav.disabled = false;

    // Update JSON Tab and Modal
    if (currentConsolidatedJSON) {
      const prettyJSON = JSON.stringify(currentConsolidatedJSON, null, 2);
      jsonCodeBlock.innerHTML = `<code>${escapeHtml(prettyJSON)}</code>`;
      modalJsonContent.innerHTML = `<code>${escapeHtml(prettyJSON)}</code>`;
      modalEnforcementText.textContent = currentConsolidatedJSON.vessel_identification_analytics?.enforcement_recommendation || "Attribution directive available.";
    }

    // 4. Populate Vessel Attribution HUD
    vesselCountBadge.textContent = `${rankedVessels.length} Tracked`;

    if (prime) {
      primeVesselName.textContent = prime.name;
      primeVesselFlag.textContent = `${prime.flag_code || ""} ${prime.flag}`;
      primeVesselType.textContent = `Type: ${prime.vessel_type}`;
      primeVesselMmsi.textContent = `MMSI: ${prime.mmsi}`;
      primeVesselSpeed.textContent = `Speed: ${prime.speed_knots} kts`;

      primeCpaDist.textContent = `${prime.distance_to_centroid_km} km`;
      primeTimeDelta.textContent = `${prime.time_delta_minutes > 0 ? "+" : ""}${prime.time_delta_minutes} min`;

      primeSuspectScore.textContent = `${prime.suspect_score.toFixed(1)}%`;
      primeScoreBar.style.width = `${Math.min(100, prime.suspect_score)}%`;

      primeRiskBadge.textContent = prime.risk_tier;
      primeRiskBadge.className = `risk-pill ${prime.risk_tier.toLowerCase().includes("critical") ? "critical" : prime.risk_tier.toLowerCase().includes("high") ? "high" : "moderate"}`;

      const rec = currentConsolidatedJSON?.vessel_identification_analytics?.enforcement_recommendation;
      primeDirectiveText.textContent = rec || `Vessel ${prime.name} passed within ${prime.distance_to_centroid_km} km of slick centroid.`;

      mapSubtitle.textContent = `Primary Suspect: ${prime.name} (${prime.suspect_score}% suspect score, ${prime.distance_to_centroid_km} km CPA)`;
    } else {
      primeVesselName.textContent = "No Vessels Correlated";
      primeDirectiveText.textContent = "No AIS vessel line tracks detected in surveillance sector.";
    }

    // 5. Build Ranked Leaderboard List
    vesselLeaderboardList.innerHTML = "";
    if (rankedVessels.length === 0) {
      vesselLeaderboardList.innerHTML = '<div class="empty-list-placeholder">No vessel trajectories in sector</div>';
    } else {
      rankedVessels.forEach((v, idx) => {
        const item = document.createElement("div");
        const isPrime = idx === 0;
        item.className = `vessel-item ${isPrime ? "prime-item active" : ""}`;

        const tierClass = v.suspect_score >= 75 ? "critical" : v.suspect_score >= 50 ? "high" : v.suspect_score >= 30 ? "moderate" : "low";

        item.innerHTML = `
          <div class="vessel-item-left">
            <span class="vessel-item-name">${isPrime ? "🚨 " : ""}${v.name}</span>
            <span class="vessel-item-sub">${v.vessel_type} &bull; ${v.distance_to_centroid_km} km CPA</span>
          </div>
          <div class="vessel-item-right">
            <span class="vessel-item-score ${tierClass}">${v.suspect_score.toFixed(1)}%</span>
            <span class="vessel-item-sub">${v.time_delta_minutes > 0 ? "+" : ""}${v.time_delta_minutes}m</span>
          </div>
        `;

        item.addEventListener("click", () => {
          document.querySelectorAll(".vessel-item").forEach((el) => el.classList.remove("active"));
          item.classList.add("active");
          focusVesselOnMap(v);
        });

        vesselLeaderboardList.appendChild(item);
      });
    }

    // 6. Render Layers on Leaflet Map
    spillLayerGroup.clearLayers();
    vesselLayerGroup.clearLayers();
    cpaLayerGroup.clearLayers();

    // A. Spill Polygons (Vibrant Red with Amber Borders)
    if (results.features && results.features.length > 0) {
      const spillGeo = {
        type: "FeatureCollection",
        features: results.features,
      };
      currentSpillLayer = L.geoJSON(spillGeo, {
        style: {
          color: "#f59e0b",
          weight: 2.5,
          opacity: 0.95,
          fillColor: "#ef4444",
          fillOpacity: 0.6,
        },
        onEachFeature: (feature, layer) => {
          const p = feature.properties;
          layer.bindPopup(`
            <div style="font-family: 'Outfit', sans-serif; font-size: 13px; color: #1e293b;">
              <h4 style="margin: 0 0 6px; color: #b91c1c;">Detected Oil Spill #${p.candidate_id}</h4>
              <table style="width: 100%; border-collapse: collapse; line-height: 1.5;">
                <tr><td><strong>Heuristic Conf:</strong></td><td style="color: #d97706;">${(p.heuristic_confidence_score * 100).toFixed(1)}%</td></tr>
                <tr><td><strong>Estimated Area:</strong></td><td>${p.estimated_area_km2} km² (${p.estimated_area_m2?.toLocaleString()} m²)</td></tr>
                <tr><td><strong>Centroid:</strong></td><td>${p.centroid_lat}°N, ${p.centroid_lon}°E</td></tr>
                <tr><td><strong>UTM Zone:</strong></td><td>${p.utm_projection}</td></tr>
              </table>
            </div>
          `);
        },
      });
      spillLayerGroup.addLayer(currentSpillLayer);

      // Instantly center and zoom map on the detected oil spill!
      if (currentSpillLayer.getBounds().isValid()) {
        map.fitBounds(currentSpillLayer.getBounds(), { padding: [40, 40], maxZoom: 13 });
      }
    }

    // B. Vessel Trajectory Lines
    if (vAnalytics.vessel_geojson && vAnalytics.vessel_geojson.features) {
      const vLayer = L.geoJSON(vAnalytics.vessel_geojson, {
        style: (feature) => {
          const p = feature.properties;
          const isPrime = prime && p.mmsi === prime.mmsi;
          if (isPrime) {
            return {
              color: "#ef4444",
              weight: 4,
              opacity: 1.0,
              dashArray: "6, 6",
            };
          } else if (p.suspect_score >= 50) {
            return {
              color: "#f59e0b",
              weight: 3,
              opacity: 0.9,
              dashArray: "4, 6",
            };
          } else {
            return {
              color: "#00d4ff",
              weight: 2,
              opacity: 0.75,
              dashArray: "3, 5",
            };
          }
        },
        onEachFeature: (feature, layer) => {
          const p = feature.properties;
          const isPrime = prime && p.mmsi === prime.mmsi;
          layer.bindPopup(`
            <div style="font-family: 'Outfit', sans-serif; font-size: 13px; color: #1e293b;">
              <h4 style="margin: 0 0 6px; color: ${isPrime ? "#b91c1c" : "#0284c7"};">
                ${isPrime ? "🚨 " : ""}${p.name}
              </h4>
              <table style="width: 100%; border-collapse: collapse; line-height: 1.5;">
                <tr><td><strong>MMSI:</strong></td><td>${p.mmsi}</td></tr>
                <tr><td><strong>Type:</strong></td><td>${p.vessel_type}</td></tr>
                <tr><td><strong>Flag:</strong></td><td>${p.flag}</td></tr>
                <tr><td><strong>Speed / Course:</strong></td><td>${p.speed_knots} kts @ ${p.heading_deg}°</td></tr>
                <tr><td><strong>Distance to Spill:</strong></td><td style="color: #b91c1c; font-weight:700;">${p.distance_to_centroid_km} km</td></tr>
                <tr><td><strong>Suspect Score:</strong></td><td style="color: #d97706; font-weight:700;">${p.suspect_score.toFixed(1)}% (${p.risk_tier})</td></tr>
                <tr><td><strong>CPA Time:</strong></td><td>${p.cpa_timestamp || "N/A"}</td></tr>
              </table>
            </div>
          `);
        },
      });
      vesselLayerGroup.addLayer(vLayer);
    }

    // C. CPA Waypoint Markers & Ship Icons
    rankedVessels.forEach((v, idx) => {
      const isPrime = idx === 0;
      const cpaLat = v.cpa_coordinates.lat;
      const cpaLon = v.cpa_coordinates.lon;

      const markerColor = isPrime ? "#ef4444" : v.suspect_score >= 50 ? "#f59e0b" : "#00d4ff";
      const markerHtml = `
        <div style="
          background: ${markerColor};
          width: ${isPrime ? "24px" : "18px"};
          height: ${isPrime ? "24px" : "18px"};
          border-radius: 50%;
          border: 2px solid #ffffff;
          box-shadow: 0 0 12px ${markerColor};
          display: flex;
          align-items: center;
          justify-content: center;
          font-size: 11px;
          color: white;
          font-weight: 700;
        ">${isPrime ? "★" : ""}</div>
      `;

      const shipIcon = L.divIcon({
        html: markerHtml,
        className: "custom-ship-icon",
        iconSize: [24, 24],
        iconAnchor: [12, 12],
      });

      const marker = L.marker([cpaLat, cpaLon], { icon: shipIcon });
      marker.bindPopup(`
        <div style="font-family: 'Outfit', sans-serif; font-size: 13px; color: #1e293b;">
          <h4 style="margin: 0 0 4px; color: ${markerColor};">${v.name} (CPA Point)</h4>
          <p style="margin: 0 0 4px; font-size: 11px;">Distance to Spill: <strong>${v.distance_to_centroid_km} km</strong></p>
          <p style="margin: 0; font-size: 11px;">Suspect Score: <strong>${v.suspect_score}%</strong></p>
        </div>
      `);
      vesselLayerGroup.addLayer(marker);
    });

    // D. CPA Distance Vectors (Line connecting vessel to spill centroid)
    if (vAnalytics.cpa_vectors_geojson && vAnalytics.cpa_vectors_geojson.features) {
      const cpaLayer = L.geoJSON(vAnalytics.cpa_vectors_geojson, {
        style: (feature) => {
          const isPrime = feature.properties.is_primary_suspect;
          return {
            color: isPrime ? "#ef4444" : "#f59e0b",
            weight: isPrime ? 3.0 : 1.8,
            dashArray: "5, 5",
            opacity: isPrime ? 1.0 : 0.65,
          };
        },
        onEachFeature: (feature, layer) => {
          const p = feature.properties;
          layer.bindTooltip(`CPA Distance: ${p.vessel_name} (${p.distance_km} km)`, { sticky: true });
        },
      });
      cpaLayerGroup.addLayer(cpaLayer);
    }
  }

  // Focus specific vessel on map
  function focusVesselOnMap(v) {
    if (!v || !v.cpa_coordinates) return;
    const lat = v.cpa_coordinates.lat;
    const lon = v.cpa_coordinates.lon;
    map.flyTo([lat, lon], 11, { duration: 1.2 });
  }

  // File drag & drop support
  ["dragenter", "dragover"].forEach((evt) => {
    dropZone.addEventListener(evt, (e) => {
      e.preventDefault();
      dropZone.classList.add("dragover");
    });
  });

  ["dragleave", "drop"].forEach((evt) => {
    dropZone.addEventListener(evt, (e) => {
      e.preventDefault();
      dropZone.classList.remove("dragover");
    });
  });

  dropZone.addEventListener("drop", (e) => {
    const files = e.dataTransfer.files;
    if (files.length > 0) uploadAndProcess(files[0]);
  });

  fileInput.addEventListener("change", (e) => {
    if (e.target.files.length > 0) uploadAndProcess(e.target.files[0]);
  });

  async function uploadAndProcess(file) {
    if (!file.name.toLowerCase().endsWith(".tif") && !file.name.toLowerCase().endsWith(".tiff")) {
      alert("Please select a valid Sentinel-1 GeoTIFF (.tif/.tiff)");
      return;
    }

    const formData = new FormData();
    formData.append("file", file);

    const promptText = dropZone.querySelector(".upload-prompt p");
    const origText = promptText.innerHTML;
    promptText.innerHTML = `<strong>Correlating ${file.name}...</strong>`;

    try {
      const resp = await fetch("/detect", {
        method: "POST",
        body: formData,
      });

      if (!resp.ok) {
        const err = await resp.json();
        alert(`Detection failed: ${err.detail || "Server error"}`);
        return;
      }

      const results = await resp.json();
      renderDetectionResults(results);
    } catch (err) {
      alert(`Upload error: ${err.message}`);
    } finally {
      promptText.innerHTML = origText;
    }
  }

  // EVENT LISTENERS FOR SELECTION AND ANALYZE BUTTON
  sampleSelect.addEventListener("change", () => {
    loadScene(sampleSelect.value);
  });

  btnRunSample.addEventListener("click", () => {
    loadScene(sampleSelect.value);
  });

  // INITIALIZATION: Populate scenes and AUTOMATICALLY LOAD 00000.tif ON PAGE LOAD!
  populateDropdownWithDefaultScenes();
  loadScene("00000.tif");

  // Also fetch updated manifest in background if available
  fetch("samples_manifest.json")
    .then((r) => r.json())
    .then((manifest) => {
      if (Array.isArray(manifest) && manifest.length > 0) {
        staticManifest = manifest;
        sampleSelect.innerHTML = "";
        manifest.forEach((item) => {
          const opt = document.createElement("option");
          opt.value = item.name;
          const primeName = item.primary_suspect_name || "Correlated";
          opt.textContent = `${item.name} (${item.detected_regions_count} slicks, ${item.total_estimated_area_km2} km² - Suspect: ${primeName})`;
          sampleSelect.appendChild(opt);
        });
        sampleSelect.value = currentResults?.name || manifest[0].name;
      }
    })
    .catch((err) => console.log("Background manifest sync:", err));

  function escapeHtml(str) {
    return str
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }
});
