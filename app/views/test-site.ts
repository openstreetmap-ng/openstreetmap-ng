import "./main.scss"

import "bootstrap"

const quizModal = document.getElementById("testSiteQuizModal")!
const quizForm = quizModal.querySelector("form")!
const submitButton = quizForm.querySelector('button[type="submit"]')!

const updateAnswerStyles = (input: HTMLInputElement) => {
  // Clear all styles for this question
  for (const radio of quizForm.querySelectorAll(`input[name="${input.name}"]`))
    radio.closest("label")!.classList.remove("text-success", "text-danger")

  // Apply style to checked input
  if (input.checked)
    input
      .closest("label")!
      .classList.add(input.value === "correct" ? "text-success" : "text-danger")
}

const checkQuizCompletion = () => {
  const allRadios = quizForm.querySelectorAll('input[type="radio"]')
  const checkedRadios = quizForm.querySelectorAll('input[type="radio"]:checked')

  const questionCount = new Set(Array.from(allRadios, (input) => input.name)).size

  const allAnswered = questionCount === checkedRadios.length
  const allCorrect = Array.from(checkedRadios).every(
    (radio) => radio.value === "correct",
  )

  submitButton.disabled = !(allAnswered && allCorrect)
}

quizForm.addEventListener("change", (e) => {
  const radio = e.target as HTMLInputElement
  if (radio.type === "radio") {
    updateAnswerStyles(radio)
    checkQuizCompletion()
  }
})

quizModal.addEventListener("hidden.bs.modal", () => {
  // Reset all inputs and styles
  for (const radio of document.querySelectorAll('input[type="radio"]')) {
    radio.checked = false
    updateAnswerStyles(radio)
  }
  checkQuizCompletion()
})
