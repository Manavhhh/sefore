/**
 * AegisSAR: Oil Spill Detection Frontend Controller
 * PS ID: SIH26143
 */

document.addEventListener("DOMContentLoaded", () => {
  // Elements
  const dropZone = document.getElementById("drop-zone");
  const fileInput = document.getElementById("file-input");
  const sampleSelect = document.getElementById("sample-select");
  const btnRunSample = document.getElementById("btn-run-sample");
  const btnResetZoom = document.getElementById("btn-reset-zoom");
  const btnDownloadGeoJSON = document.getElementById("btn-download-geojson");

  // Metric displays
  const metricRegions = document.getElementById("metric-regions");
  const metricConfidence = document.getElementById("metric-confidence");
  const metricArea = document.getElementById("metric-area");
  const metricCoords = document.getElementById("metric-coords");

  // Imagery panels
  const imgOverlay = document.getElementById("img-overlay");
  const imgMask = document.getElementById("img-mask");
  const imgSar = document.getElementById("img-sar");

  // Tabs
  const tabBtns = document.querySelectorAll(".tab-btn");
  const tabPanels = document.querySelectorAll(".tab-panel");

  // State
  let currentGeoJSON = null;
  let geojsonLayer = null;

  // Initialize Leaflet Map
  const map = L.map("leaflet-map", {
    center: [55.33, 3.97], // Default to North Sea area
    zoom: 7,
    attributionControl: true,
  });

  // 100% Free Public Basemaps (No API key required)
  const osmLayer = L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    maxZoom: 19,
  });

  const esriOcean = L.tileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/Ocean/World_Ocean_Base/MapServer/tile/{z}/{y}/{x}", {
    attribution: 'Tiles &copy; Esri &mdash; Sources: GEBCO, NOAA, CHS, OSU, UNH, CSUMB, National Geographic, DeLorme, NAVTEQ, and Esri',
    maxZoom: 13,
  });

  const esriSat = L.tileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}", {
    attribution: 'Tiles &copy; Esri &mdash; Source: Esri, i-cubed, USDA, USGS, AEX, GeoEye, Getmapping, Aerogrid, IGN, IGP, UPR-EGP, and the GIS User Community',
    maxZoom: 18,
  });

  // Add OpenStreetMap as default
  osmLayer.addTo(map);

  // Basemap selector control
  L.control.layers({
    "OpenStreetMap": osmLayer,
    "Esri Ocean Basemap": esriOcean,
    "Satellite Imagery": esriSat,
  }, null, { position: "topright" }).addTo(map);

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

  let staticManifest = null;

  // Load available Zenodo samples (supports both live FastAPI and static Netlify)
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
      console.log("FastAPI backend not detected, checking static manifest for Netlify hosting...");
    }

    // Static Netlify Fallback
    try {
      const mResp = await fetch("samples_manifest.json");
      if (mResp.ok) {
        staticManifest = await mResp.json();
        sampleSelect.innerHTML = "";
        staticManifest.forEach((item) => {
          const opt = document.createElement("option");
          opt.value = item.name;
          opt.textContent = `${item.name} (${item.detected_regions_count} spills, ${item.total_estimated_area_km2} km²)`;
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

  // Reset / Fit Zoom to Spill Polygon
  btnResetZoom.addEventListener("click", () => {
    if (geojsonLayer && geojsonLayer.getBounds().isValid()) {
      map.fitBounds(geojsonLayer.getBounds(), { padding: [40, 40] });
    }
  });

  // Download GeoJSON
  btnDownloadGeoJSON.addEventListener("click", () => {
    if (staticManifest) {
      const selected = staticManifest.find((i) => i.name === sampleSelect.value);
      if (selected) {
        window.location.href = selected.geojson_url;
        return;
      }
    }
    window.location.href = "/download/geojson";
  });

  // Handle Drag & Drop
  ["dragenter", "dragover"].forEach((eventName) => {
    dropZone.addEventListener(eventName, (e) => {
      e.preventDefault();
      dropZone.classList.add("dragover");
    });
  });

  ["dragleave", "drop"].forEach((eventName) => {
    dropZone.addEventListener(eventName, (e) => {
      e.preventDefault();
      dropZone.classList.remove("dragover");
    });
  });

  dropZone.addEventListener("drop", (e) => {
    const files = e.dataTransfer.files;
    if (files.length > 0) {
      uploadAndProcess(files[0]);
    }
  });

  fileInput.addEventListener("change", (e) => {
    if (e.target.files.length > 0) {
      uploadAndProcess(e.target.files[0]);
    }
  });

  // Run selected Zenodo sample (supports both live API and static Netlify)
  btnRunSample.addEventListener("click", async () => {
    const sample = sampleSelect.value;
    if (!sample) return;

    btnRunSample.disabled = true;
    btnRunSample.textContent = "Processing...";

    // Check if static manifest is active (Netlify mode)
    if (staticManifest) {
      const item = staticManifest.find((i) => i.name === sample);
      if (item) {
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

  // Upload GeoTIFF via POST /detect
  async function uploadAndProcess(file) {
    if (!file.name.toLowerCase().endsWith(".tif") && !file.name.toLowerCase().endsWith(".tiff")) {
      alert("Please select a valid Sentinel-1 GeoTIFF (.tif/.tiff)");
      return;
    }

    const formData = new FormData();
    formData.append("file", file);

    const promptText = dropZone.querySelector(".upload-prompt p");
    const origText = promptText.innerHTML;
    promptText.innerHTML = `<strong>Processing ${file.name}...</strong>`;

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

  // Render Pipeline Results onto Map and Dashboard
  function renderDetectionResults(results, isStatic = false) {
    console.log("Detection results received:", results);

    // Update HUD Metrics
    metricRegions.textContent = results.detected_regions_count;
    metricConfidence.textContent = results.highest_confidence ? (results.highest_confidence * 100).toFixed(1) + "%" : "--";
    metricArea.textContent = `${results.total_estimated_area_km2} km²`;

    if (results.features && results.features.length > 0) {
      const f = results.features[0];
      const p = f.properties;
      metricCoords.textContent = `${p.centroid_lat.toFixed(4)}°N, ${p.centroid_lon.toFixed(4)}°E`;
    } else {
      metricCoords.textContent = "None";
    }

    btnDownloadGeoJSON.disabled = !results.features || results.features.length === 0;

    // Update Imagery Views
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

    // Render GeoJSON on Leaflet
    if (geojsonLayer) {
      map.removeLayer(geojsonLayer);
    }

    const featureCollection = {
      type: "FeatureCollection",
      features: results.features || [],
    };

    currentGeoJSON = featureCollection;

    geojsonLayer = L.geoJSON(featureCollection, {
      style: (feature) => ({
        color: "#f59e0b", // Glowing amber border
        weight: 2.5,
        opacity: 0.95,
        fillColor: "#ef4444", // Vibrant red fill for suspected spill
        fillOpacity: 0.5,
      }),
      onEachFeature: (feature, layer) => {
        const p = feature.properties;
        const popupContent = `
          <div style="font-family: 'Outfit', sans-serif; color: #1e293b; font-size: 13px;">
            <h4 style="margin: 0 0 6px; color: #b91c1c;">Spill Candidate #${p.candidate_id}</h4>
            <table style="width: 100%; border-collapse: collapse; line-height: 1.5;">
              <tr><td><strong>Heuristic Conf:</strong></td><td style="color: #d97706;">${(p.heuristic_confidence_score * 100).toFixed(1)}%</td></tr>
              <tr><td><strong>Estimated Area:</strong></td><td>${p.estimated_area_km2} km² (${p.estimated_area_m2.toLocaleString()} m²)</td></tr>
              <tr><td><strong>Centroid:</strong></td><td>${p.centroid_lat}°N, ${p.centroid_lon}°E</td></tr>
              <tr><td><strong>Projection:</strong></td><td>${p.utm_projection}</td></tr>
            </table>
            <p style="margin: 6px 0 0; font-size: 10px; color: #64748b;">${p.note}</p>
          </div>
        `;
        layer.bindPopup(popupContent);
      },
    }).addTo(map);

    if (geojsonLayer.getBounds().isValid()) {
      map.fitBounds(geojsonLayer.getBounds(), { padding: [50, 50], maxZoom: 13 });
    }
  }
});
