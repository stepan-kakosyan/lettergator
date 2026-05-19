(function () {
  var scenariosElement = document.getElementById("cg-scenarios-data");
  if (!scenariosElement) { return; }

  var SCENARIOS = {};
  var labels = {};

  try {
    var scenariosPayload = JSON.parse(scenariosElement.textContent);
    SCENARIOS = scenariosPayload || {};
    labels = SCENARIOS.labels || {};
  } catch (error) {
    return;
  }

  var ctaEl   = document.getElementById("cg-cta-href");
  var ctaHref = ctaEl ? ctaEl.getAttribute("data-href") : "/letters/";

  function cap(s) { return s.charAt(0).toUpperCase() + s.slice(1); }

  function renderDetail(scenario, cat, detailEl) {
    detailEl.innerHTML =
      '<span class="detail-tag ' + cat + '">' + cap(cat) + '</span>' +
      '<div class="detail-title">' + scenario.title + '</div>' +
      '<p class="detail-story">' + scenario.story + '</p>' +
      '<div class="detail-meta">' +
        '<div class="meta-item"><span class="meta-label">' + labels.timing + '</span>' +
          '<span class="meta-value">' + scenario.timing + '</span></div>' +
        '<div class="meta-item"><span class="meta-label">' + labels.audience + '</span>' +
          '<span class="meta-value">' + scenario.audience + '</span></div>' +
        '<div class="meta-item"><span class="meta-label">' + labels.delivery + '</span>' +
          '<span class="meta-value">' + scenario.delivery + '</span></div>' +
      '</div>' +
      '<a href="' + ctaHref + '" class="detail-cta">' + labels.writeCta + ' &rarr;</a>';
  }

  function initSection(cat) {
    var listEl   = document.getElementById("list-" + cat);
    var detailEl = document.getElementById("detail-" + cat);
    if (!listEl || !detailEl) { return; }

    var list = SCENARIOS[cat] || [];

    list.forEach(function (scenario, i) {
      var row = document.createElement("button");
      row.type = "button";
      row.className = "cg-scenario-row" + (i === 0 ? " is-active" : "");
      row.dataset.cat = cat;
      row.innerHTML =
        '<span class="row-title">' + scenario.title + '</span>' +
        '<span class="row-teaser">' + scenario.teaser + '</span>';

      row.addEventListener("click", function () {
        listEl.querySelectorAll(".cg-scenario-row").forEach(function (r) {
          r.classList.remove("is-active");
        });
        row.classList.add("is-active");
        renderDetail(scenario, cat, detailEl);
      });

      listEl.appendChild(row);
    });

    renderDetail(list[0], cat, detailEl);
  }

  Object.keys(SCENARIOS).forEach(function (category) {
    if (category !== "labels") {
      initSection(category);
    }
  });
})();
