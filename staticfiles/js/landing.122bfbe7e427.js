(function () {
  function initLandingTimeline() {
    const cards = document.querySelectorAll(".timeline-card[data-step]");
    const kicker = document.getElementById("timeline-kicker");
    const title = document.getElementById("timeline-title");
    const body = document.getElementById("timeline-body");

    if (!cards.length || !kicker || !title || !body) {
      return;
    }

    const steps = {
      draft: {
        kicker: "Compose",
        title: "Create a meaningful letter in minutes.",
        body:
          "Add a clear subject and your full message. The letter is attached "
          + "to your account and ready for secure scheduling.",
      },
      seal: {
        kicker: "Seal",
        title: "Choose privacy and ownership controls.",
        body:
          "Decide if you can preview content before delivery and whether edit "
          + "or delete actions are allowed in the first month.",
      },
      schedule: {
        kicker: "Schedule",
        title: "Set exact timing for emotional impact.",
        body:
          "Pick the precise delivery date and time. Quick slots help you set "
          + "future milestones like 1 month, 1 year, or 10 years ahead.",
      },
      deliver: {
        kicker: "Deliver",
        title: "Automatic delivery with fallback reliability.",
        body:
          "LetterGator sends to your selected recipients when the clock hits. "
          + "If a primary route fails, fallback logic protects delivery success.",
      },
    };

    function activate(stepKey) {
      const content = steps[stepKey];
      if (!content) {
        return;
      }

      cards.forEach((card) => {
        card.classList.toggle("is-active", card.dataset.step === stepKey);
      });
      kicker.textContent = content.kicker;
      title.textContent = content.title;
      body.textContent = content.body;
    }

    cards.forEach((card) => {
      card.addEventListener("click", function () {
        activate(this.dataset.step);
      });
    });
  }

  function initCreateLetterForm() {
    const form = document.getElementById("vault-form");
    const sendToMe = document.getElementById("id_send_to_me");
    const deliveryAt = document.getElementById("id_delivery_at");
    const recipientPanel = document.getElementById("recipient-panel");
    const recipientInputs = document.getElementById("recipient-inputs");
    const recipientList = document.getElementById("id_recipient_list");
    const browserTimezone = document.getElementById("id_browser_timezone");
    const addRecipient = document.getElementById("add-recipient");
    const helper = document.getElementById("recipient-helper");

    if (
      !form
      || !sendToMe
      || !recipientPanel
      || !recipientInputs
      || !recipientList
      || !browserTimezone
      || !addRecipient
      || !helper
    ) {
      return;
    }

    function setBrowserTimezone() {
      const tz = Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC";
      browserTimezone.value = tz;
    }

    const MAX_RECIPIENTS = 5;

    function initBinaryToggles() {
      const toggleGroups = document.querySelectorAll("[data-toggle-field]");

      toggleGroups.forEach((group) => {
        const fieldId = group.getAttribute("data-toggle-field");
        const checkbox = document.getElementById(fieldId);
        const buttons = group.querySelectorAll("[data-toggle-value]");

        if (!checkbox || !buttons.length) {
          return;
        }

        function syncButtons() {
          buttons.forEach((button) => {
            const expected = button.getAttribute("data-toggle-value") === "true";
            const active = checkbox.checked === expected;
            button.classList.toggle("is-active", active);
            button.setAttribute("aria-pressed", active ? "true" : "false");
          });
        }

        buttons.forEach((button) => {
          button.addEventListener("click", function () {
            checkbox.checked = this.getAttribute("data-toggle-value") === "true";
            checkbox.dispatchEvent(new Event("change", { bubbles: true }));
            syncButtons();
          });
        });

        checkbox.addEventListener("change", syncButtons);
        syncButtons();
      });
    }

    function formatForDateTimeLocal(dateValue) {
      const year = dateValue.getFullYear();
      const month = String(dateValue.getMonth() + 1).padStart(2, "0");
      const day = String(dateValue.getDate()).padStart(2, "0");
      const hours = String(dateValue.getHours()).padStart(2, "0");
      const minutes = String(dateValue.getMinutes()).padStart(2, "0");
      return `${year}-${month}-${day}T${hours}:${minutes}`;
    }

    function initDatePresets() {
      if (!deliveryAt) {
        return;
      }

      const presetButtons = document.querySelectorAll("[data-date-months]");

      presetButtons.forEach((button) => {
        button.addEventListener("click", function () {
          const monthOffset = Number(this.getAttribute("data-date-months"));
          const targetDate = new Date();
          targetDate.setMonth(targetDate.getMonth() + monthOffset);

          deliveryAt.value = formatForDateTimeLocal(targetDate);
          deliveryAt.dispatchEvent(new Event("change", { bubbles: true }));

          presetButtons.forEach((item) => item.classList.remove("is-active"));
          this.classList.add("is-active");
        });
      });
    }

    function syncRecipientList() {
      const values = Array.from(
        recipientInputs.querySelectorAll("input[data-recipient]"),
      )
        .map((input) => input.value.trim())
        .filter(Boolean);

      recipientList.value = values.join(",");
    }

    function refreshAddButtonState() {
      const count = recipientInputs.querySelectorAll("input[data-recipient]").length;
      addRecipient.disabled = count >= MAX_RECIPIENTS;
      addRecipient.classList.toggle("opacity-40", addRecipient.disabled);
      addRecipient.classList.toggle("cursor-not-allowed", addRecipient.disabled);
    }

    function createRecipientInput(value) {
      const row = document.createElement("div");
      row.className = "recipient-input-row";

      const input = document.createElement("input");
      input.type = "email";
      input.dataset.recipient = "1";
      input.placeholder = "recipient@example.com";
      input.value = value || "";
      input.required = !sendToMe.checked;

      const removeButton = document.createElement("button");
      removeButton.type = "button";
      removeButton.className = "recipient-remove";
      removeButton.textContent = "Remove";

      removeButton.addEventListener("click", function () {
        row.remove();
        syncRecipientList();
        refreshAddButtonState();
        ensureOneRecipientWhenNeeded();
      });

      input.addEventListener("input", syncRecipientList);

      row.appendChild(input);
      row.appendChild(removeButton);
      recipientInputs.appendChild(row);
      refreshAddButtonState();
    }

    function ensureOneRecipientWhenNeeded() {
      const hasRecipient = recipientInputs.querySelector("input[data-recipient]");
      if (!sendToMe.checked && !hasRecipient) {
        createRecipientInput("");
      }
    }

    function toggleRecipientPanel() {
      const isSendToMe = sendToMe.checked;
      recipientPanel.classList.toggle("hidden", isSendToMe);
      helper.textContent = isSendToMe
        ? ""
        : "Add at least one recipient when 'Send to me' is disabled.";

      recipientInputs.querySelectorAll("input[data-recipient]").forEach((input) => {
        input.required = !isSendToMe;
      });

      ensureOneRecipientWhenNeeded();
      syncRecipientList();
    }

    addRecipient.addEventListener("click", function () {
      createRecipientInput("");
      syncRecipientList();
    });

    sendToMe.addEventListener("change", toggleRecipientPanel);

    form.addEventListener("submit", function (event) {
      syncRecipientList();

      const recipientsCount = recipientList.value
        ? recipientList.value.split(",").filter(Boolean).length
        : 0;

      if (!sendToMe.checked && recipientsCount === 0) {
        event.preventDefault();
        helper.textContent = "Please add at least one recipient email.";
        return;
      }

      if (recipientsCount > MAX_RECIPIENTS) {
        event.preventDefault();
        helper.textContent = "Maximum 5 recipient emails are allowed.";
      }
    });

    initBinaryToggles();
    setBrowserTimezone();
    initDatePresets();
    toggleRecipientPanel();
  }

  function initLettersPageInteractions() {
    const viewModal = document.getElementById("view-modal");
    const viewTitle = document.getElementById("view-title");
    const viewBody = document.getElementById("view-body");
    const editModal = document.getElementById("edit-modal");
    const editSubject = document.getElementById("edit-subject");
    const editForm = document.getElementById("edit-form");
    const editTextarea = document.getElementById("edit-textarea");

    if (
      !viewModal
      || !viewTitle
      || !viewBody
      || !editModal
      || !editSubject
      || !editForm
      || !editTextarea
    ) {
      return;
    }

    const viewOpeners = document.querySelectorAll("[data-view-open]");
    const viewClosers = viewModal.querySelectorAll("[data-view-close]");
    const editOpeners = document.querySelectorAll("[data-edit-open]");
    const editClosers = editModal.querySelectorAll("[data-edit-close]");
    let currentEditLetterId = null;

    function decodeMessageText(rawText) {
      if (!rawText) {
        return "";
      }

      return rawText
        .replace(/\\u000D\\u000A/g, "\n")
        .replace(/\\u000A/g, "\n")
        .replace(/\\u000D/g, "\n")
        .replace(/\\r\\n/g, "\n")
        .replace(/\\n/g, "\n")
        .replace(/\\r/g, "\n");
    }

    function closeViewModal() {
      viewModal.classList.add("hidden");
      viewModal.setAttribute("aria-hidden", "true");
      viewBody.textContent = "";
    }

    function closeEditModal() {
      editModal.classList.add("hidden");
      editModal.setAttribute("aria-hidden", "true");
      currentEditLetterId = null;
      editForm.action = "";
      editSubject.textContent = "";
      editTextarea.value = "";
    }

    viewOpeners.forEach((button) => {
      button.addEventListener("click", function () {
        viewTitle.textContent = this.getAttribute("data-view-title") || "Letter";
        viewBody.textContent = decodeMessageText(
          this.getAttribute("data-view-message") || "",
        );
        viewModal.classList.remove("hidden");
        viewModal.setAttribute("aria-hidden", "false");
      });
    });

    viewClosers.forEach((button) => {
      button.addEventListener("click", closeViewModal);
    });

    editOpeners.forEach((button) => {
      button.addEventListener("click", function () {
        currentEditLetterId = this.getAttribute("data-edit-id");
        editForm.action = this.getAttribute("data-edit-url") || "";
        editSubject.textContent = this.getAttribute("data-edit-subject") || "";
        editTextarea.value = decodeMessageText(
          this.getAttribute("data-edit-message") || "",
        );
        editModal.classList.remove("hidden");
        editModal.setAttribute("aria-hidden", "false");
        editTextarea.focus();
      });
    });

    editClosers.forEach((button) => {
      button.addEventListener("click", closeEditModal);
    });

    document.addEventListener("keydown", function (event) {
      if (event.key !== "Escape") {
        return;
      }
      if (!viewModal.classList.contains("hidden")) {
        closeViewModal();
      }
      if (!editModal.classList.contains("hidden")) {
        closeEditModal();
      }
    });

    editForm.addEventListener("submit", function (event) {
      event.preventDefault();
      if (!editForm.action || !currentEditLetterId) {
        return;
      }

      const formData = new FormData(editForm);
      fetch(editForm.action, {
        method: "POST",
        headers: {
          "X-Requested-With": "XMLHttpRequest",
        },
        body: formData,
      })
        .then((response) => response.json())
        .then((payload) => {
          if (!payload.ok) {
            window.alert(payload.error || "Unable to update letter text.");
            return;
          }

          const excerpt = document.querySelector(
            `[data-content-excerpt-id="${currentEditLetterId}"]`,
          );
          if (excerpt) {
            excerpt.textContent = payload.excerpt;
          }

          const editButton = document.querySelector(
            `[data-edit-open][data-edit-id="${currentEditLetterId}"]`,
          );

          if (editButton) {
            editButton.setAttribute("data-edit-message", payload.message);
          }

          const row = document.querySelector(`tr[data-letter-id="${currentEditLetterId}"]`);
          if (row) {
            const rowViewButton = row.querySelector("[data-view-open]");
            if (rowViewButton) {
              rowViewButton.setAttribute("data-view-message", payload.message);
            }
          }

          closeEditModal();
        })
        .catch(() => {
          window.alert("Unable to update letter text.");
        });
    });
  }

  initCreateLetterForm();
  initLettersPageInteractions();
  initLandingTimeline();
})();
