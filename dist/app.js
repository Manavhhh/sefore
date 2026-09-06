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

  // Leaflet Map & Layer Groups
  const map = L.map("leaflet-map", {
    center: [55.33, 3.97],
    zoom: 7,
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

  // Layer toggle event listeners
  toggleLayerSpill.addEventListener("change", (e) => {
    if (e.target.checked) map.addLayer(spillLayerGroup);
    else map.removeLayer(spillLayerGroup);
  });

  toggleLayerVessels.addEventListener("change", (e) => {
    if (e.target.checked) map.addLayer(vesselLayerGroup);
    else map.removeLayer(vesselLayerGroup);
  });

  toggleLayerCpa.addEventListener("change", (e) => {
    if (e.target.checked) map.addLayer(cpaLayerGroup);
    else map.removeLayer(cpaLayerGroup);
  });

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

  btnCopyJson.addEventListener("click", () => copyJSONToClipboard(btnCopyJson));
  btnModalCopy.addEventListener("click", () => copyJSONToClipboard(btnModalCopy));

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

  btnDownloadConsolidated.addEventListener("click", downloadConsolidatedJSON);
  btnDownloadTabJson.addEventListener("click", downloadConsolidatedJSON);
  btnModalDownload.addEventListener("click", downloadConsolidatedJSON);

  // Download Spill GeoJSON
  btnDownloadGeoJSON.addEventListener("click", () => {
    if (staticManifest) {
      const selected = staticManifest.find((i) => i.name === sampleSelect.value);
      if (selected && selected.geojson_url) {
        window.location.href = selected.geojson_url;
        return;
      }
    }
    window.location.href = "/download/geojson";
  });

  // Fit bounds actions
  btnFitSpill.addEventListener("click", () => {
    const layers = spillLayerGroup.getLayers();
    if (layers.length > 0 && layers[0].getBounds && layers[0].getBounds().isValid()) {
      map.fitBounds(layers[0].getBounds(), { padding: [50, 50], maxZoom: 13 });
    }
  });

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

  // Load Zenodo test samples (FastAPI live or static Netlify)
  async function loadSamples() {
    try {
      const resp = await fetch("/sample-list");
      if (resp.ok) {
        const data = await resp.json();
        sampleSelect.innerHTML = "";
        if (data.samples && data.samples.length > 0) {
          data.samples.forEach((name) => {
            const opt = document.createElement("option");
            opt.value = name;
            opt.textContent = name;
            sampleSelect.appendChild(opt);
          });
          return;
        }
      }
    } catch (err) {
      console.log("Live backend not detected, checking static manifest...");
    }

    try {
      const mResp = await fetch("samples_manifest.json");
      if (mResp.ok) {
        staticManifest = await mResp.json();
        sampleSelect.innerHTML = "";
        staticManifest.forEach((item) => {
          const opt = document.createElement("option");
          opt.value = item.name;
          const primeName = item.vessel_analytics?.primary_suspect?.name || "Correlated";
          opt.textContent = `${item.name} (${item.detected_regions_count} slicks, ${item.total_estimated_area_km2} km² - Suspect: ${primeName})`;
          sampleSelect.appendChild(opt);
        });
        const statusPill = document.getElementById("system-status");
        if (statusPill) {
          statusPill.innerHTML = '<span class="status-dot"></span> Netlify Showcase Active';
        }
      }
    } catch (mErr) {
      console.warn("Could not load static manifest:", mErr);
      sampleSelect.innerHTML = '<option value="">No samples found</option>';
    }
  }

  loadSamples();

  // Run selected Zenodo sample
  btnRunSample.addEventListener("click", async () => {
    const sample = sampleSelect.value;
    if (!sample) return;

    btnRunSample.disabled = true;
    btnRunSample.textContent = "Correlating...";

    if (staticManifest) {
      const item = staticManifest.find((i) => i.name === sample);
      if (item) {
        // Fetch static final_spill_data.json if present
        let consolidatedData = null;
        if (item.final_spill_data_url) {
          try {
            const fjResp = await fetch(item.final_spill_data_url);
            if (fjResp.ok) consolidatedData = await fjResp.json();
          } catch (e) {
            console.warn("Could not fetch static final_spill_data:", e);
          }
        }
        item.consolidated_analytics = consolidatedData;
        renderDetectionResults(item, true);
        btnRunSample.disabled = false;
        btnRunSample.textContent = "Analyze";
        return;
      }
    }

    try {
      const resp = await fetch(`/detect-sample/${encodeURIComponent(sample)}`);
      if (!resp.ok) {
        const err = await resp.json();
        alert(`Detection failed: ${err.detail || "Server error"}`);
        return;
      }
      const results = await resp.json();
      renderDetectionResults(results);
    } catch (err) {
      alert(`Network error: ${err.message}`);
    } finally {
      btnRunSample.disabled = false;
      btnRunSample.textContent = "Analyze";
    }
  });

  // File drag & drop
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

  // Render Full Pipeline & Vessel Attribution Results
  function renderDetectionResults(results, isStatic = false) {
    console.log("Full Detection & AIS Attribution Results:", results);
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

    // 3. Extract Vessel Analytics & Consolidated Analytics
    const vAnalytics = results.vessel_analytics || {};
    const prime = vAnalytics.primary_suspect;
    const rankedVessels = vAnalytics.ranked_suspects || [];

    // Synthesize or extract consolidated analytics JSON
    if (results.consolidated_analytics) {
      currentConsolidatedJSON = results.consolidated_analytics;
    } else {
      currentConsolidatedJSON = {
        version: "2.0-SIH26143",
        module: "Sefore Satellite SAR & AIS Maritime Identification Engine",
        scene_metadata: {
          source_image: results.name || results.source_image,
          coordinate_reference_system: "EPSG:4326",
        },
        spill_detection_summary: {
          detected_regions_count: results.detected_regions_count,
          total_estimated_area_km2: results.total_estimated_area_km2,
          total_estimated_area_m2: results.total_estimated_area_m2,
          highest_heuristic_confidence: results.highest_confidence,
          primary_centroid: centroidLat ? { lat: centroidLat, lon: centroidLon } : null,
        },
        spill_features: results.features || [],
        vessel_identification_analytics: {
          total_vessels_tracked: rankedVessels.length,
          prime_suspect_vessel: prime,
          ranked_suspect_leaderboard: rankedVessels,
          enforcement_recommendation: prime ? `HIGH ALERT: Vessel ${prime.name} passed within ${prime.distance_to_centroid_km} km of the slick centroid. Suspect Index: ${prime.suspect_score}%.` : "No vessels identified in immediate vicinity.",
        }
      };
    }

    // Enable JSON Actions
    btnDownloadConsolidated.disabled = false;
    btnOpenModalNav.disabled = false;

    // Update JSON Tab and Modal
    const prettyJSON = JSON.stringify(currentConsolidatedJSON, null, 2);
    jsonCodeBlock.innerHTML = `<code>${escapeHtml(prettyJSON)}</code>`;
    modalJsonContent.innerHTML = `<code>${escapeHtml(prettyJSON)}</code>`;
    modalEnforcementText.textContent = currentConsolidatedJSON.vessel_identification_analytics?.enforcement_recommendation || "Attribution completed.";

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

      const rec = currentConsolidatedJSON.vessel_identification_analytics?.enforcement_recommendation;
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

    // A. Spill Polygons
    if (results.features && results.features.length > 0) {
      const spillGeo = {
        type: "FeatureCollection",
        features: results.features,
      };
      const spillLayer = L.geoJSON(spillGeo, {
        style: {
          color: "#f59e0b",
          weight: 2.5,
          opacity: 0.95,
          fillColor: "#ef4444",
          fillOpacity: 0.55,
        },
        onEachFeature: (feature, layer) => {
          const p = feature.properties;
          layer.bindPopup(`
            <div style="font-family: 'Outfit', sans-serif; font-size: 13px; color: #1e293b;">
              <h4 style="margin: 0 0 6px; color: #b91c1c;">Detected Spill #${p.candidate_id}</h4>
              <table style="width: 100%; border-collapse: collapse; line-height: 1.5;">
                <tr><td><strong>Heuristic Conf:</strong></td><td style="color: #d97706;">${(p.heuristic_confidence_score * 100).toFixed(1)}%</td></tr>
                <tr><td><strong>Estimated Area:</strong></td><td>${p.estimated_area_km2} km²</td></tr>
                <tr><td><strong>Centroid:</strong></td><td>${p.centroid_lat}°N, ${p.centroid_lon}°E</td></tr>
                <tr><td><strong>UTM Zone:</strong></td><td>${p.utm_projection}</td></tr>
              </table>
            </div>
          `);
        },
      });
      spillLayerGroup.addLayer(spillLayer);
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
              opacity: 0.7,
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
          width: ${isPrime ? "22px" : "16px"};
          height: ${isPrime ? "22px" : "16px"};
          border-radius: 50%;
          border: 2px solid #ffffff;
          box-shadow: 0 0 12px ${markerColor};
          display: flex;
          align-items: center;
          justify-content: center;
          font-size: 10px;
          color: white;
          font-weight: 700;
        ">${isPrime ? "★" : ""}</div>
      `;

      const shipIcon = L.divIcon({
        html: markerHtml,
        className: "custom-ship-icon",
        iconSize: [22, 22],
        iconAnchor: [11, 11],
      });

      const marker = L.marker([cpaLat, cpaLon], { icon: shipIcon });
      marker.bindPopup(`
        <div style="font-family: 'Outfit', sans-serif; font-size: 13px; color: #1e293b;">
          <h4 style="margin: 0 0 4px; color: ${markerColor};">${v.name} (CPA Point)</h4>
          <p style="margin: 0 0 4px; font-size: 11px;">Distance to Spill Centroid: <strong>${v.distance_to_centroid_km} km</strong></p>
          <p style="margin: 0; font-size: 11px;">Suspect Score: <strong>${v.suspect_score}%</strong></p>
        </div>
      `);
      vesselLayerGroup.addLayer(marker);
    });

    // D. CPA Distance Vectors (Line from CPA to Spill Centroid)
    if (vAnalytics.cpa_vectors_geojson && vAnalytics.cpa_vectors_geojson.features) {
      const cpaLayer = L.geoJSON(vAnalytics.cpa_vectors_geojson, {
        style: (feature) => {
          const isPrime = feature.properties.is_primary_suspect;
          return {
            color: isPrime ? "#ef4444" : "#f59e0b",
            weight: isPrime ? 2.5 : 1.5,
            dashArray: "4, 4",
            opacity: isPrime ? 0.95 : 0.6,
          };
        },
        onEachFeature: (feature, layer) => {
          const p = feature.properties;
          layer.bindTooltip(`CPA Vector: ${p.vessel_name} (${p.distance_km} km to centroid)`, { sticky: true });
        },
      });
      cpaLayerGroup.addLayer(cpaLayer);
    }

    // Auto-fit bounds
    btnFitSpill.click();
  }

  // Focus specific vessel on map
  function focusVesselOnMap(v) {
    if (!v || !v.cpa_coordinates) return;
    const lat = v.cpa_coordinates.lat;
    const lon = v.cpa_coordinates.lon;
    map.flyTo([lat, lon], 11, { duration: 1.2 });
  }

  // HTML escape utility
  function escapeHtml(str) {
    return str
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }
});
