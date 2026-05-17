import { Controller } from "@hotwired/stimulus"

export default class extends Controller {
  static targets = ["output"]

  displayFiles(event) {
    const files = Array.from(event.target.files)
      .filter((file) => /\.(png|jpe?g|webp)$/i.test(file.name))
      .sort((first, second) => first.name.localeCompare(second.name))

    if (files.length === 0) {
      this.outputTarget.innerHTML = '<p class="file-list-empty">No .png, .jpg, or .webp files found.</p>'
      return
    }

    const rows = files.map((file) => {
      const path = file.webkitRelativePath || file.name
      const updatedAt = new Date(file.lastModified).toLocaleString([], {
        dateStyle: "medium",
        timeStyle: "short"
      })

      return `
        <li class="file-list-row">
          <span class="file-name">${this.escapeHtml(path)}</span>
          <time class="file-time" datetime="${new Date(file.lastModified).toISOString()}">${updatedAt}</time>
        </li>
      `
    }).join("")

    this.outputTarget.innerHTML = `
      <h2>Image Files</h2>
      <ul class="file-list-items">
        ${rows}
      </ul>
    `
  }

  escapeHtml(value) {
    return value.replace(/[&<>"']/g, (character) => ({
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      '"': "&quot;",
      "'": "&#39;"
    }[character]))
  }
}
