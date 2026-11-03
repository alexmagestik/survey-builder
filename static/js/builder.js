(function () {
  const form = document.getElementById("survey-form");
  if (!form) return;

  const questionsContainer = document.getElementById("questions");
  const addQuestionBtn = document.getElementById("add-question");
  const questionTemplate = document.getElementById("question-template");
  const optionTemplate = document.getElementById("option-template");
  const scoringToggle = document.getElementById("scoring-toggle");

  function renumber() {
    const cards = questionsContainer.querySelectorAll("[data-question]");
    cards.forEach(function (card, qIndex) {
      const number = card.querySelector(".question-number");
      if (number) number.textContent = qIndex + 1;

      const textInput = card.querySelector('input[name$="-text"]');
      if (textInput) textInput.name = "questions-" + qIndex + "-text";

      const typeSelect = card.querySelector('select[name$="-type"]');
      if (typeSelect) typeSelect.name = "questions-" + qIndex + "-type";

      const requiredInput = card.querySelector('input[name$="-required"]');
      if (requiredInput) requiredInput.name = "questions-" + qIndex + "-required";

      const allowOtherInput = card.querySelector('input[name$="-allow-other"]');
      if (allowOtherInput) allowOtherInput.name = "questions-" + qIndex + "-allow-other";

      const optionRows = card.querySelectorAll("[data-option]");
      optionRows.forEach(function (row, oIndex) {
        const optionText = row.querySelector('input[name$="-text"]');
        if (optionText) {
          optionText.name = "questions-" + qIndex + "-options-" + oIndex + "-text";
        }
        const optionCorrect = row.querySelector('input[name$="-correct"]');
        if (optionCorrect) {
          optionCorrect.name = "questions-" + qIndex + "-options-" + oIndex + "-correct";
        }
      });
    });
  }

  function addOption(card) {
    const optionsList = card.querySelector("[data-options]");
    if (!optionsList) return;
    optionsList.appendChild(optionTemplate.content.cloneNode(true));
  }

  function updateQuestionState(card) {
    const typeSelect = card.querySelector('select[name$="-type"]');
    if (!typeSelect) return;
    const isChoice = typeSelect.value !== "text";
    const optionsList = card.querySelector("[data-options]");
    const addOptionBtn = card.querySelector(".add-option");
    const allowOtherInput = card.querySelector('input[name$="-allow-other"]');

    if (optionsList) optionsList.style.display = isChoice ? "" : "none";
    if (addOptionBtn) addOptionBtn.style.display = isChoice ? "" : "none";
    if (allowOtherInput) {
      allowOtherInput.disabled = !isChoice;
      if (!isChoice) allowOtherInput.checked = false;
    }

    if (isChoice && optionsList) {
      while (optionsList.querySelectorAll("[data-option]").length < 2) {
        addOption(card);
      }
    }
  }

  function updateScoring() {
    if (!scoringToggle) return;
    form.classList.toggle("scoring-on", scoringToggle.checked);
  }

  questionsContainer.querySelectorAll("[data-question]").forEach(function (card) {
    updateQuestionState(card);
  });
  updateScoring();

  if (addQuestionBtn) {
    addQuestionBtn.addEventListener("click", function () {
      questionsContainer.appendChild(questionTemplate.content.cloneNode(true));
      const card = questionsContainer.lastElementChild;
      addOption(card);
      addOption(card);
      updateQuestionState(card);
      renumber();
    });
  }

  questionsContainer.addEventListener("click", function (event) {
    const removeQuestion = event.target.closest(".remove-question");
    if (removeQuestion) {
      const card = removeQuestion.closest("[data-question]");
      const count = questionsContainer.querySelectorAll("[data-question]").length;
      if (count <= 1) {
        window.alert("Должен остаться хотя бы один вопрос.");
        return;
      }
      card.remove();
      renumber();
      return;
    }

    const addOptionBtn = event.target.closest(".add-option");
    if (addOptionBtn) {
      const card = addOptionBtn.closest("[data-question]");
      addOption(card);
      renumber();
      return;
    }

    const removeOption = event.target.closest(".remove-option");
    if (removeOption) {
      const row = removeOption.closest("[data-option]");
      const card = row.closest("[data-question]");
      const rows = card.querySelectorAll("[data-option]");
      if (rows.length <= 2) {
        window.alert("Для вопроса с выбором нужно минимум два варианта.");
        return;
      }
      row.remove();
      renumber();
    }
  });

  questionsContainer.addEventListener("change", function (event) {
    if (event.target.matches('select[name$="-type"]')) {
      updateQuestionState(event.target.closest("[data-question]"));
    }
  });

  if (scoringToggle) {
    scoringToggle.addEventListener("change", updateScoring);
  }
})();
