require "fileutils"
require "json"
require "open3"
require "securerandom"

class StabilizerController < ApplicationController
  def stabilize
  end

  def upload
    images = uploaded_images
    job_id = SecureRandom.hex(12)
    job_dir = Rails.root.join("tmp", "stabilizer_jobs", job_id)
    input_dir = job_dir.join("input")
    output_path = job_dir.join("timelapse.mp4")
    metadata_path = job_dir.join("metadata.json")
    status_path = job_dir.join("status.json")

    FileUtils.mkdir_p(input_dir)
    File.write(status_path, JSON.generate({ status: "queued", progress: 0, message: "Saving images..." }))

    metadata_by_name = JSON.parse(params[:timelapse_metadata].presence || "[]").index_by do |item|
      File.basename(item["name"].to_s)
    end

    images.each_with_index do |image, index|
      extension = File.extname(image.original_filename).downcase
      saved_name = format("%06d%s", index, extension)
      FileUtils.cp(image.tempfile.path, input_dir.join(saved_name))

      metadata_item = metadata_by_name[File.basename(image.original_filename)]
      metadata_item["name"] = saved_name if metadata_item
    end

    File.write(metadata_path, JSON.pretty_generate(metadata_by_name.values.compact))

    start_render_job(input_dir, metadata_path, output_path, status_path)

    respond_to do |format|
      format.json { render json: { job_id: job_id } }
      format.html { redirect_to stabilize_path, notice: "Rendering started." }
    end
  end

  def status
    status_path = job_dir_for(params[:job_id]).join("status.json")

    if File.exist?(status_path)
      render json: JSON.parse(File.read(status_path))
    else
      render json: { status: "missing", progress: 0, message: "Render job was not found." }, status: :not_found
    end
  end

  def video
    output_path = job_dir_for(params[:job_id]).join("timelapse.mp4")

    if File.exist?(output_path)
      send_file output_path, type: "video/mp4", disposition: "inline"
    else
      head :not_found
    end
  end

  private

  def uploaded_images
    Array(params[:timelapse_folder]).select do |file|
      file.respond_to?(:original_filename) &&
        file.original_filename.match?(/\.(png|jpe?g|webp)\z/i)
    end
  end

  def start_render_job(input_dir, metadata_path, output_path, status_path)
    script_path = Rails.root.join("script", "render_timelapse.py")

    Thread.new do
      _stdout, stderr, wait_status = Open3.capture3(
        "/opt/homebrew/bin/python3",
        script_path.to_s,
        input_dir.to_s,
        metadata_path.to_s,
        output_path.to_s,
        status_path.to_s
      )

      next if wait_status.success?

      File.write(status_path, JSON.generate({
        status: "error",
        progress: 0,
        message: stderr.presence || "Video render failed."
      }))
    end
  end

  def job_dir_for(job_id)
    Rails.root.join("tmp", "stabilizer_jobs", job_id.to_s.gsub(/[^a-f0-9]/, ""))
  end
end
