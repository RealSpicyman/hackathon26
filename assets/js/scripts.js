document.addEventListener("DOMContentLoaded", function () {
  // Initialize Bootstrap Tooltips
  var tooltipTriggerList = [].slice.call(
    document.querySelectorAll('[data-bs-toggle="tooltip"]'),
  );
  var tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
    return new bootstrap.Tooltip(tooltipTriggerEl);
  });
});

// ================= API BASE RESOLVER =================
function resolveApiBase() {
  const params = new URLSearchParams(window.location.search);
  const apiBaseParam = params.get("apiBase");

  if (apiBaseParam) {
    return apiBaseParam.replace(/\/$/, "");
  }

  if (
    window.location.protocol === "http:" ||
    window.location.protocol === "https:"
  ) {
    return window.location.origin;
  }

  return "http://127.0.0.1:8000";
}

const apiBase = resolveApiBase();
const isNgrokRequest = /ngrok-free\.app|ngrok\.io/i.test(apiBase);
const defaultFetchOptions = isNgrokRequest
  ? { headers: { "ngrok-skip-browser-warning": "true" } }
  : {};

// ================= DOM ELEMENTS =================
// Stage Elements
const stage1 = document.getElementById("stage-1");
const mainContent = document.getElementById("main-content");
const stage2 = document.getElementById("stage-2");
const stage3 = document.getElementById("stage-3");
const startBtn = document.getElementById("start-btn");

// Form Elements
const form = document.getElementById("search-form");
const input = document.getElementById("address-input");
const addressOptions = document.getElementById("custom-address-options");
const searchButton = form.querySelector("button");
const statusText = document.getElementById("status-text");
const multiAddressHint = document.getElementById("multi-address-hint");
const multiAddressInfoBtn = document.getElementById("multi-address-info-btn");
const multiAddressPopup = document.getElementById("multi-address-popup");
const multiAddressCloseBtn = document.getElementById("multi-address-close-btn");
const multiAddressList = document.getElementById("multi-address-list");
const hasBootstrap = typeof bootstrap !== "undefined";
const multiAddressModal =
  hasBootstrap && multiAddressPopup
    ? new bootstrap.Modal(multiAddressPopup)
    : null;
let multiAddressTooltip = null;
let suggestAbortController = null;
let suggestRequestId = 0;

// AI Panel Elements
const aiPanel = document.getElementById("ai-panel");
const aiForm = document.getElementById("ai-form");
const aiSqft = document.getElementById("ai-sqft");
const aiYear = document.getElementById("ai-year");
const aiType = document.getElementById("ai-type");
const aiSubmitBtn = document.getElementById("ai-submit-btn");

// Result Panel Elements
const resultPanel = document.getElementById("result-panel");
const resultStatus = document.getElementById("result-status");
const resultTitle = document.getElementById("result-title");
const resultBadge = document.getElementById("result-badge");
const resultAddress = document.getElementById("result-address");
const resultType = document.getElementById("result-type");
const resultSqft = document.getElementById("result-sqft");
const resultGrade = document.getElementById("result-grade");
const resultConfidence = document.getElementById("result-confidence");

window.currentDisplayName = "";
window.currentAddressMatches = [];

// ================= STAGE ANIMATION LOGIC =================

// Handle Start Button (Transition Stage 1 -> Stage 2)
startBtn.addEventListener("click", () => {
  stage1.classList.remove("visible");
  setTimeout(() => {
    stage1.classList.add("d-none");
    mainContent.classList.remove("d-none");

    // Allow CSS transition to catch the block display state
    setTimeout(() => {
      stage2.classList.add("visible");
      input.focus(); // Auto-focus input for UX
    }, 50);
  }, 600); // Matches CSS transition duration
});

let hideTimeout;

// Hides Stage 3 smoothly
function resetPanels() {
  stage3.classList.remove("visible");
  hideTimeout = setTimeout(() => {
    aiPanel.classList.add("d-none");
    resultPanel.classList.add("d-none");
  }, 600);
}

// Swaps which panel is visible inside Stage 3 and fades it in
function revealPanel(panelToShow) {
  clearTimeout(hideTimeout);
  aiPanel.classList.add("d-none");
  resultPanel.classList.add("d-none");

  panelToShow.classList.remove("d-none");

  setTimeout(() => {
    stage3.classList.add("visible");
  }, 50);
}

// ================= HELPER FUNCTIONS =================
function setMultiAddressTooltip(totalMatches) {
  if (!multiAddressInfoBtn) return;

  const title =
    totalMatches > 1
      ? `Show ${totalMatches} matched addresses`
      : "Show all matched addresses";

  multiAddressInfoBtn.setAttribute("title", title);
  multiAddressInfoBtn.setAttribute("aria-label", title);

  if (!hasBootstrap) return;

  if (multiAddressTooltip) {
    multiAddressTooltip.dispose();
  }
  multiAddressTooltip = new bootstrap.Tooltip(multiAddressInfoBtn);
}

function hideMultipleAddressHint() {
  multiAddressHint.classList.add("d-none");
}

function showMultipleAddressHint(addresses) {
  window.currentAddressMatches = Array.isArray(addresses) ? addresses : [];
  if (window.currentAddressMatches.length > 1) {
    setMultiAddressTooltip(window.currentAddressMatches.length);
    multiAddressHint.classList.remove("d-none");
  } else {
    hideMultipleAddressHint();
  }
}

function openMultipleAddressPopup() {
  if (
    !window.currentAddressMatches ||
    window.currentAddressMatches.length === 0
  )
    return;

  multiAddressList.innerHTML = "";
  window.currentAddressMatches.forEach((address) => {
    const li = document.createElement("li");
    li.textContent = address;
    multiAddressList.appendChild(li);
  });

  if (multiAddressModal) {
    multiAddressModal.show();
  } else if (multiAddressPopup) {
    multiAddressPopup.classList.remove("d-none");
  }
}

function closeMultipleAddressPopup() {
  if (multiAddressModal) {
    multiAddressModal.hide();
  } else if (multiAddressPopup) {
    multiAddressPopup.classList.add("d-none");
  }
}

function setLoading(isLoading) {
  input.disabled = isLoading;
  searchButton.disabled = isLoading;
  searchButton.innerHTML = isLoading
    ? '<span class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span> Searching...'
    : "Search";
}

function showMessage(message, isError = false) {
  statusText.textContent = message;
  statusText.classList.toggle("text-danger", isError);
  statusText.classList.toggle("text-muted", !isError);
}

function showResult(data) {
  // Trigger animation to show Result panel
  revealPanel(resultPanel);

  if (data.status === "found_in_database") {
    resultStatus.innerHTML =
      '<i class="bi bi-check-circle me-1"></i>Matched record';
    resultBadge.textContent = "Verified Data";
    resultBadge.className = "badge rounded-pill bg-success text-white";
  } else if (data.status === "ai_predicted") {
    resultStatus.innerHTML =
      '<i class="bi bi-robot me-1"></i>AI Estimate';
    resultBadge.textContent = "AI Prediction";
    resultBadge.className = "badge rounded-pill bg-info text-dark";
  }

  if (data.multipleLocations) {
    resultTitle.classList.add("d-none");
    resultStatus.classList.add("d-none");
    resultBadge.classList.add("d-none");
  } else {
    resultTitle.classList.remove("d-none");
    resultStatus.classList.remove("d-none");
    resultBadge.classList.remove("d-none");
    resultTitle.textContent = data.name || "Property";
  }

  resultAddress.textContent = data.address || input.value.trim().toUpperCase();
  resultType.textContent = data.type || "-";
  resultSqft.textContent = data.sqft ? Number(data.sqft).toLocaleString() : "-";
  resultGrade.textContent = data.grade || "-";

  if (data.grade === "A")
    resultGrade.className = "d-block fs-5 fw-bold text-success";
  else if (data.grade === "B")
    resultGrade.className = "d-block fs-5 fw-bold text-primary";
  else if (data.grade === "C")
    resultGrade.className = "d-block fs-5 fw-bold text-warning";
  else if (data.grade === "D")
    resultGrade.className = "d-block fs-5 fw-bold text-danger";

  const sourceInfo = data.confidence || "AI Prediction";
  resultConfidence.textContent = `${sourceInfo} | Location: ${window.currentCoords || "N/A"}`;
}

function clearSuggestions() {
  addressOptions.innerHTML = "";
  addressOptions.classList.remove("show");
}

window.selectSuggestion = function (event, value) {
  event.preventDefault();
  input.value = value;
  clearSuggestions();
};

document.addEventListener("click", function (event) {
  if (!input.contains(event.target) && !addressOptions.contains(event.target)) {
    clearSuggestions();
  }
});

// ================= CORE API FUNCTIONS =================
async function updateAddressSuggestions() {
  const query = input.value.trim();
  if (query.length < 5) {
    clearSuggestions();
    return;
  }

  suggestRequestId += 1;
  const currentRequestId = suggestRequestId;

  if (suggestAbortController) {
    suggestAbortController.abort();
  }
  suggestAbortController = new AbortController();

  try {
    const url = `${apiBase}/api/suggest?query=${encodeURIComponent(query)}`;
    const response = await fetch(url, {
      ...defaultFetchOptions,
      signal: suggestAbortController.signal,
    });

    if (!response.ok) throw new Error("Suggestion request failed.");
    const data = await response.json();

    if (currentRequestId !== suggestRequestId) return;

    const suggestions = Array.isArray(data?.suggestions)
      ? data.suggestions
      : [];
    clearSuggestions();

    if (suggestions.length > 0) {
      addressOptions.classList.add("show");
      suggestions.forEach((suggestion) => {
        const li = document.createElement("li");
        const escapedSuggestion = suggestion
          .replace(/'/g, "\\'")
          .replace(/"/g, "&quot;");

        li.innerHTML = `
                            <a class="dropdown-item d-flex align-items-center py-2 px-3" href="#" onclick="selectSuggestion(event, '${escapedSuggestion}')">
                                <div class="flex-shrink-0 me-3">
                                    <img src="https://placehold.co/48x48/eff2f7/495057?text=B" alt="Building" class="rounded bg-light border" style="width: 40px; height: 40px; object-fit: cover;">
                                </div>
                                <div class="flex-grow-1 overflow-hidden">
                                    <h6 class="mb-0 text-truncate font-size-15 fw-semibold text-dark">${suggestion}</h6>
                                    <p class="text-muted mb-0 small text-truncate">Philadelphia, PA</p>
                                </div>
                            </a>
                        `;
        addressOptions.appendChild(li);
      });
    }
  } catch (error) {
    if (error.name === "AbortError") return;
    clearSuggestions();
    console.error(error);
  }
}

async function runSearch() {
  const query = input.value.trim();
  if (!query) return;

  setLoading(true);
  showMessage("Searching the dataset...");

  // Initiate exit animation for Stage 3
  resetPanels();

  hideMultipleAddressHint();
  clearSuggestions();

  try {
    const url = `${apiBase}/api/search?address=${encodeURIComponent(query)}`;
    const response = await fetch(url, defaultFetchOptions);
    const data = await response.json();

    if (!response.ok) throw new Error("Search request failed.");

    if (data?.error || !data) {
      showMessage("Address not in database. Geocoding location...", false);

      try {
        const geoUrl = `https://nominatim.openstreetmap.org/search?format=json&q=${encodeURIComponent(query + ", Philadelphia, PA")}&limit=8`;
        const geoResponse = await fetch(geoUrl, {
          headers: { "User-Agent": "PhillyPropertySearchApp/1.0" },
        });
        const geoData = await geoResponse.json();

        if (geoData && geoData.length > 0) {
          const { lat, lon, display_name } = geoData[0];
          const allMatches = geoData
            .map((item) =>
              typeof item.display_name === "string"
                ? item.display_name.trim()
                : "",
            )
            .filter(Boolean);

          window.currentCoords = `${lat}, ${lon}`;
          window.currentDisplayName =
            typeof display_name === "string"
              ? display_name.split(",")[0].trim()
              : "";

          showMultipleAddressHint(allMatches);

          if (allMatches.length > 1) {
            showMessage(
              `Multiple addresses found. Using first match at ${lat}, ${lon}.`,
              false,
            );
          } else {
            showMessage(
              `Located at ${lat}, ${lon}. Please provide building details.`,
              false,
            );
          }
        } else {
          window.currentCoords = "Coordinates not found";
          window.currentDisplayName = "";
          window.currentAddressMatches = [];
          hideMultipleAddressHint();
          showMessage(
            "Record not found and couldn't geocode. Enter details manually.",
            true,
          );
        }
      } catch (geoErr) {
        console.error("Geocoding error:", geoErr);
        window.currentCoords = "Geocoding service unavailable";
        window.currentDisplayName = "";
        window.currentAddressMatches = [];
        hideMultipleAddressHint();
      }

      // Animate AI Form Panel in
      revealPanel(aiPanel);
      return;
    }

    window.currentCoords = "Verified Database Record";
    window.currentDisplayName = "";
    window.currentAddressMatches = [];
    hideMultipleAddressHint();

    showResult(data);
    showMessage(`Showing exact match from city dataset.`);
  } catch (error) {
    console.error(error);
    showMessage(error.message || "Unable to reach the API.", true);
  } finally {
    setLoading(false);
  }
}

async function runAIPrediction() {
  const sqft = aiSqft.value;
  const year = aiYear.value;
  const type = aiType.value;

  const coords =
    window.currentCoords && window.currentCoords.includes(",")
      ? window.currentCoords.split(",")
      : [39.9526, -75.1652];

  aiSubmitBtn.disabled = true;
  aiSubmitBtn.innerHTML =
    '<span class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span> Calculating...';

  try {
    const url = `${apiBase}/api/predict?sqft=${sqft}&year_built=${year}&property_type=${encodeURIComponent(type)}&lat=${coords[0].trim()}&lon=${coords[1].trim()}`;
    const response = await fetch(url, defaultFetchOptions);
    const data = await response.json();

    if (data.error) throw new Error(data.error);

    if (window.currentDisplayName && window.currentAddressMatches.length <= 1) {
      data.name = window.currentDisplayName;
    }

    // Cross-fade to final result smoothly
    resetPanels();
    setTimeout(() => {
      showResult(data);
      showMessage(`AI Prediction successfully generated.`);
    }, 600);
  } catch (error) {
    console.error(error);
    alert("AI Error: " + error.message);
  } finally {
    aiSubmitBtn.disabled = false;
    aiSubmitBtn.textContent = "Predict Grade with AI";
  }
}

// ================= EVENT LISTENERS =================
form.addEventListener("submit", function (event) {
  event.preventDefault();
  runSearch();
});

input.addEventListener("input", function () {
  updateAddressSuggestions();
});

input.addEventListener("keydown", function (event) {
  if (event.key === "Escape") clearSuggestions();
});

aiForm.addEventListener("submit", function (event) {
  event.preventDefault();
  runAIPrediction();
});

if (multiAddressInfoBtn) {
  setMultiAddressTooltip(0);
  multiAddressInfoBtn.addEventListener("click", openMultipleAddressPopup);
}

if (multiAddressCloseBtn) {
  multiAddressCloseBtn.addEventListener("click", closeMultipleAddressPopup);
}
