class StabilizerController < ApplicationController
  def stabilize
  end

  def upload
    # Takes in the files, and only keeps the images, and saves it to @images
    @images = Array(params[:timelapse_folder]).select do |file|
      file.respond_to?(:original_filename) &&
        file.original_filename.match?(/\.(png|jpe?g|webp)\z/i)
    end

    @images.each do |image|
      puts image.original_filename
    end

    render :stabilize
  end
end
