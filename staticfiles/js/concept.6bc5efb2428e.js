(function () {
  var SCENARIOS = {
    personal: [
      {
        title: "To my future self",
        teaser: "Written in doubt, read in clarity.",
        story: "A letter composed during uncertainty or transition — a job change, a move, a breakup — scheduled to arrive one or five years later when the dust has settled. It becomes a mirror of who you were and proof of how far you have come.",
        timing: "1 – 5 years",
        audience: "Yourself",
        delivery: "Single recipient, self-addressed, preview blocked."
      },
      {
        title: "Before I quit my job",
        teaser: "The words you dare not say out loud today.",
        story: "Written the night before handing in a resignation, this letter captures every fear and every reason. Delivered six months after leaving, it reads either as validation of a brave decision or as a reminder of what that courage cost.",
        timing: "6 months",
        audience: "Yourself",
        delivery: "Single recipient, edits blocked after 24 hours, deletion blocked."
      },
      {
        title: "To the person I'll become",
        teaser: "A bet on your own potential.",
        story: "A ten-year letter to a future version of yourself you can only imagine. It describes current values, fears, dreams, and open questions — then delivers them on a decade milestone to be read with the context only time can provide.",
        timing: "10 years",
        audience: "Yourself",
        delivery: "Single recipient, preview blocked, no edits or deletions permitted."
      },
      {
        title: "Before my first therapy session",
        teaser: "Capture the version of you that asked for help.",
        story: "Written before starting a new chapter of personal work, this letter records the raw starting point — the confusion, the hope, the specific things you want to change. Delivered a year later, it documents the distance between who you were and who you became.",
        timing: "1 year",
        audience: "Yourself",
        delivery: "Single recipient, private, preview blocked, edits locked immediately."
      }
    ],
    family: [
      {
        title: "To my partner",
        teaser: "Timed for the moment it will mean the most.",
        story: "A private note written today but scheduled for a meaningful anniversary, a birthday, or a difficult stretch ahead. It arrives when presence matters most, carrying words chosen in a quieter, more intentional moment.",
        timing: "Exact anniversary date",
        audience: "Partner",
        delivery: "Primary + secondary fallback, preview allowed, edits open for 30 days."
      },
      {
        title: "To my newborn child",
        teaser: "Words that will wait eighteen years.",
        story: "Written in the first weeks of parenthood, when everything feels enormous and fragile, and delivered on a child's eighteenth birthday. It preserves the awe and love of a moment that time would otherwise soften into vague memory.",
        timing: "18 years",
        audience: "Child",
        delivery: "Primary + trusted secondary route, all edits and deletion blocked after 90 days."
      },
      {
        title: "To my family",
        teaser: "Across distance, across time, care arrives anyway.",
        story: "A long-horizon letter written during a family milestone — a move abroad, a health scare, a reunion — scheduled for a future birthday, holiday, or anniversary. It bridges the gap that geography or time might otherwise widen.",
        timing: "1 – 3 years",
        audience: "Multiple family members",
        delivery: "Multiple recipients, fallback addresses enabled, preview allowed."
      }
    ],
    team: [
      {
        title: "To my team on launch day",
        teaser: "The message they'll open when the hard part is over.",
        story: "Written weeks before a product launch while pressure and doubt are highest. Delivered the morning the product goes live, it reminds every team member of the original intent and celebrates the collective effort at the exact moment it lands.",
        timing: "Exact launch date",
        audience: "Full team",
        delivery: "Multiple recipients, delivery blocked until scheduled date, no early access."
      },
      {
        title: "To the next team lead",
        teaser: "Pass on what experience taught you.",
        story: "A knowledge transfer letter written by a departing lead and delivered to their successor on their first day or at the three-month mark. It captures institutional wisdom, hidden context, and honest advice that no handover doc ever fully contains.",
        timing: "30 – 90 days after handover",
        audience: "Successor or new hire",
        delivery: "Single recipient, preview blocked, edits allowed for 14 days."
      },
      {
        title: "To the team in one year",
        teaser: "A commitment written before anyone can be sure.",
        story: "Written at the start of a new year or strategic cycle, this letter captures the team's goals and shared agreements and delivers them twelve months later as a candid retrospective prompt. It makes intentions visible before results arrive.",
        timing: "1 year",
        audience: "Full team",
        delivery: "Multiple recipients, preview blocked, no edits after initial submission."
      }
    ],
    milestone: [
      {
        title: "Before I retire",
        teaser: "Everything you learned, preserved at the moment of leaving.",
        story: "Written on the final working day, this letter captures career lessons, advice for the next generation, and a reflection on the work that mattered most. Delivered years later to a mentee or former colleague, it turns departure into a lasting gift.",
        timing: "1 – 5 years post-retirement",
        audience: "Mentee or former colleague",
        delivery: "Single or multiple recipients, long-horizon scheduling, edits allowed for 30 days."
      },
      {
        title: "Before moving abroad",
        teaser: "The home you're leaving deserves a proper goodbye.",
        story: "Written the night before an international move while the weight of the decision is still raw. Delivered one year into the new life, it reads as a time capsule of who you were before the world got wider — the fears, the excitement, the specific reasons that made you go.",
        timing: "1 year",
        audience: "Yourself or close friends",
        delivery: "Self-addressed or multiple, secondary contacts enabled."
      },
      {
        title: "On a difficult anniversary",
        teaser: "Grief doesn't follow a calendar, but love can.",
        story: "Written in a moment of clarity and care, scheduled to arrive on a date that someone you know will find difficult — a loss, a health anniversary, an old wound. It does not try to fix anything; it simply makes sure they know they are not alone on that day.",
        timing: "Exact annual date",
        audience: "Friend or family member",
        delivery: "Single recipient, fallback secondary address, preview blocked, edits closed after sending."
      }
    ]
  };

  var ctaEl   = document.getElementById("cg-cta-href");
  var ctaHref = ctaEl ? ctaEl.getAttribute("data-href") : "/letters/";

  function cap(s) { return s.charAt(0).toUpperCase() + s.slice(1); }

  function renderDetail(scenario, cat, detailEl) {
    detailEl.innerHTML =
      '<span class="detail-tag ' + cat + '">' + cap(cat) + '</span>' +
      '<div class="detail-title">' + scenario.title + '</div>' +
      '<p class="detail-story">' + scenario.story + '</p>' +
      '<div class="detail-meta">' +
        '<div class="meta-item"><span class="meta-label">Typical timing</span>' +
          '<span class="meta-value">' + scenario.timing + '</span></div>' +
        '<div class="meta-item"><span class="meta-label">Audience</span>' +
          '<span class="meta-value">' + scenario.audience + '</span></div>' +
        '<div class="meta-item"><span class="meta-label">Delivery setup</span>' +
          '<span class="meta-value">' + scenario.delivery + '</span></div>' +
      '</div>' +
      '<a href="' + ctaHref + '" class="detail-cta">Write this letter &rarr;</a>';
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

  ["personal", "family", "team", "milestone"].forEach(initSection);
})();
