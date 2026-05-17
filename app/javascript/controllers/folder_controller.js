import { Controller } from "@hotwired/stimulus"

export default class extends Controller {
  static targets = ["metadata", "message", "output", "progress", "progressBar", "video"]

  displayFiles(event) {
    const files = Array.from(event.target.files)
      .filter((file) => /\.(png|jpe?g|webp)$/i.test(file.name))
      .sort((first, second) => first.lastModified - second.lastModified)

    this.metadataTarget.value = JSON.stringify(files.map((file) => ({
      name: file.name,
      path: file.webkitRelativePath || file.name,
      lastModified: file.lastModified
    })))

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

  async submit(event) {
    event.preventDefault()

    this.showProgress(0, "Uploading images to Ruby...")
    this.videoTarget.hidden = true
    this.videoTarget.removeAttribute("src")

    const response = await fetch(this.element.action, {
      method: this.element.method,
      body: new FormData(this.element),
      headers: {
        Accept: "application/json"
      }
    })

    if (!response.ok) {
      this.showProgress(0, "Upload failed.")
      return
    }

    const data = await response.json()
    this.pollStatus(data.job_id)
  }

  async pollStatus(jobId) {
    const response = await fetch(`/stabilize/status/${jobId}`, {
      headers: { Accept: "application/json" }
    })
    const data = await response.json()

    this.showProgress(data.progress || 0, data.message || "Rendering...")

    if (data.status === "complete") {
      this.videoTarget.src = `/stabilize/video/${jobId}`
      this.videoTarget.hidden = false
      this.videoTarget.load()
      return
    }

    if (data.status === "error" || data.status === "missing") {
      return
    }

    window.setTimeout(() => this.pollStatus(jobId), 750)
  }

  showProgress(progress, message) {
    this.progressTarget.hidden = false
    this.progressBarTarget.value = progress
    this.messageTarget.textContent = message
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
