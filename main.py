import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from PIL import Image, ImageTk, ImageDraw, ImageFilter, ImageChops


class ImageProcessorApp(tk.Tk):
    def __init__(self):
        super().__init__()

        self.title("DeepFaceLab: Process Merge")

        # Variables
        self.curr_dir = tk.StringVar()
        self.current_image_number = tk.IntVar(value=1)
        self.canvas_zoom = tk.IntVar(value=30)  # Default canvas zoom size in percentage
        self.original_image = None
        self.data_dst_image = None  # Original data_dst image
        self.modified_image = None  # Merged image (modified image)
        self.right_frame_width = 250
        self.max_canvas_size = self.calculate_canvas_size()
        self.traced_path = []  # Store the points of the traced path
        self.trace_line_ids = []  # Store the line IDs of the traced path
        self.previous_image_state = None  # Store previous state for undo
        self.scale_factor = 1  # Store the scaling factor for mapping coordinates
        self.zoom_rect = None  # Store the rectangle for zoom
        self.is_zoomed = False  # Flag to track zoom state
        self.zoomed_region = None  # Store the zoomed region coordinates
        self.current_image = "Merged Image"  # Track which image is currently shown
        self.smoothing_var = tk.BooleanVar(value=False)  # Smoothing option checkbox variable
        self.feather_radius = tk.IntVar(value=3)  # Feather radius for smoothing effect
        self.use_original_backup_var = tk.BooleanVar(value=True)  # Backup option for "Use Original" operation

        # Continuous advancement variables
        self.is_advancing = False  # Flag to indicate continuous advancement
        self.advance_delay = tk.IntVar(
            value=100)  # Delay in milliseconds between image loads during continuous advancement

        # GUI Layout
        self.create_widgets()

    def calculate_canvas_size(self):
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        zoom_factor = self.canvas_zoom.get() / 100
        canvas_width = int(screen_width * zoom_factor)
        canvas_height = int(screen_height * zoom_factor)
        return canvas_width, canvas_height

    def create_widgets(self):
        # Left Frame for directory selection and image controls
        left_frame = tk.Frame(self)
        left_frame.pack(side=tk.LEFT, fill=tk.Y, padx=10, pady=10)

        tk.Button(left_frame, text="Select Image Directory", command=self.select_directory).pack(pady=5)

        tk.Label(left_frame, text="Current Image Number:").pack()
        current_entry = tk.Entry(left_frame, textvariable=self.current_image_number)
        current_entry.pack(pady=5)
        current_entry.bind("<Return>", lambda event: self.load_image())

        tk.Label(left_frame, text="Canvas Zoom (%)").pack()
        canvas_zoom_entry = tk.Entry(left_frame, textvariable=self.canvas_zoom)
        canvas_zoom_entry.pack(pady=5)
        canvas_zoom_entry.bind("<Return>", lambda event: self.adjust_canvas_zoom())

        # Center Frame for canvas and navigation controls
        center_frame = tk.Frame(self)
        center_frame.pack(side=tk.LEFT, expand=True, fill=tk.BOTH)

        # Set initial canvas size based on the zoom percentage
        self.canvas = tk.Canvas(center_frame, bg='white', width=self.max_canvas_size[0], height=self.max_canvas_size[1])
        self.canvas.pack(expand=False, fill=tk.NONE)

        nav_frame = tk.Frame(center_frame)
        nav_frame.pack(side=tk.TOP, fill=tk.X)

        # Previous Scan button (continuous backward advancement)
        self.prev_scan_button = tk.Button(nav_frame, text="Previous Scan")
        self.prev_scan_button.pack(side=tk.LEFT, padx=10, pady=10)
        self.prev_scan_button.bind("<ButtonPress-1>", self.start_previous_image_loop)
        self.prev_scan_button.bind("<ButtonRelease-1>", self.stop_image_loop)

        # Previous Image button (single backward advancement)
        self.prev_button = tk.Button(nav_frame, text="Previous Image")
        self.prev_button.pack(side=tk.LEFT, padx=10, pady=10)
        self.prev_button.bind("<ButtonPress-1>", lambda event: self.previous_image())

        # Next Image button (single forward advancement)
        self.next_button = tk.Button(nav_frame, text="Next Image")
        self.next_button.pack(side=tk.LEFT, padx=10, pady=10)
        self.next_button.bind("<ButtonPress-1>", lambda event: self.next_image())

        # Forward Scan button (continuous forward advancement)
        self.next_scan_button = tk.Button(nav_frame, text="Forward Scan")
        self.next_scan_button.pack(side=tk.LEFT, padx=10, pady=10)
        self.next_scan_button.bind("<ButtonPress-1>", self.start_next_image_loop)
        self.next_scan_button.bind("<ButtonRelease-1>", self.stop_image_loop)

        # Speed control entry box and image number/total images display
        tk.Label(nav_frame, text="Speed (ms):").pack(side=tk.LEFT, padx=5)
        speed_entry = tk.Entry(nav_frame, textvariable=self.advance_delay, width=5)
        speed_entry.pack(side=tk.LEFT, padx=5)
        speed_entry.bind("<Return>", lambda event: self.update_speed())
        speed_entry.bind("<Return>", lambda event: self.focus_set())  # Remove focus from entry on Enter key

        self.image_num_label = tk.Label(nav_frame, text="0/0")
        self.image_num_label.pack(side=tk.LEFT, padx=10)

        self.progress_bar = ttk.Progressbar(nav_frame, orient="horizontal", length=200, mode="determinate")
        self.progress_bar.pack(side=tk.LEFT, padx=10)

        # Bind canvas click to advance the image (initially active)
        self.canvas.bind("<Button-1>", lambda event: self.next_image())

        # Right Frame for processing controls
        self.right_frame = tk.Frame(self, width=self.right_frame_width)
        self.right_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=10, pady=10)

        self.process_button = tk.Button(self.right_frame, text="Process Image", command=self.process_image)
        self.process_button.pack(pady=5)

        # Skeletons for the rest of the buttons
        self.image_selector_label = tk.Label(self.right_frame, text="Select Image:")
        self.image_selector = ttk.Combobox(self.right_frame, textvariable=tk.StringVar(value="Merged Image"),
                                           values=["Merged Image", "Original Image"])
        self.image_selector.bind("<<ComboboxSelected>>", self.update_displayed_image)

        self.zoom_button = tk.Button(self.right_frame, text="Zoom", command=self.start_zoom_mode)
        self.reset_zoom_button = tk.Button(self.right_frame, text="Reset Zoom", command=self.reset_zoom)
        self.trace_button = tk.Button(self.right_frame, text="Trace", command=self.start_trace_mode)
        self.copy_button = tk.Button(self.right_frame, text="Copy", command=self.copy_traced_area)
        self.undo_button = tk.Button(self.right_frame, text="Undo", command=self.undo_last_action)
        self.save_button = tk.Button(self.right_frame, text="Save", command=self.save_image)

        self.backup_var = tk.BooleanVar(value=True)  # Backup option checkbox
        self.backup_checkbox = tk.Checkbutton(self.right_frame, text="Make Backup", variable=self.backup_var)

        self.smoothing_checkbox = tk.Checkbutton(self.right_frame, text="Apply Smoothing", variable=self.smoothing_var,
                                                 command=self.toggle_feather_radius)
        self.feather_radius_label = tk.Label(self.right_frame, text="Feather Radius:")
        self.feather_radius_entry = tk.Entry(self.right_frame, textvariable=self.feather_radius, width=5)

        # "Use Original" button and backup option
        self.use_original_button = tk.Button(self.right_frame, text="Use Original", command=self.use_original_image)
        self.use_original_backup_checkbox = tk.Checkbutton(self.right_frame, text="Backup on Use Original",
                                                           variable=self.use_original_backup_var)

        # Keep Tools Visible checkbox
        self.keep_tools_visible_var = tk.BooleanVar(value=False)
        self.keep_tools_visible_checkbox = tk.Checkbutton(self.right_frame, text="Keep Tools Visible",
                                                          variable=self.keep_tools_visible_var)
        self.keep_tools_visible_checkbox.pack(side=tk.BOTTOM, pady=10)

        self.toggle_right_frame_controls(False)  # Initially hide right frame controls

        # Ensure the canvas click only advances one image at a time
        self.canvas.bind("<Button-1>", lambda event: self.next_image())

    def toggle_right_frame_controls(self, show):
        if show or self.keep_tools_visible_var.get():  # Keep tools visible if the checkbox is checked
            self.image_selector_label.pack(pady=5)
            self.image_selector.pack(pady=5)
            self.zoom_button.pack(pady=5)
            self.reset_zoom_button.pack(pady=5)
            self.trace_button.pack(pady=5)
            self.copy_button.pack(pady=5)
            self.undo_button.pack(pady=5)
            self.smoothing_checkbox.pack(pady=5)
            if self.smoothing_var.get():
                self.feather_radius_label.pack(pady=5)
                self.feather_radius_entry.pack(pady=5)
            self.backup_checkbox.pack(pady=5)
            self.save_button.pack(pady=5)
            self.use_original_button.pack(pady=5)
            self.use_original_backup_checkbox.pack(pady=5)
        else:
            self.image_selector_label.pack_forget()
            self.image_selector.pack_forget()
            self.zoom_button.pack_forget()
            self.reset_zoom_button.pack_forget()
            self.trace_button.pack_forget()
            self.copy_button.pack_forget()
            self.undo_button.pack_forget()
            self.smoothing_checkbox.pack_forget()
            self.feather_radius_label.pack_forget()
            self.feather_radius_entry.pack_forget()
            self.backup_checkbox.pack_forget()
            self.save_button.pack_forget()
            self.use_original_button.pack_forget()
            self.use_original_backup_checkbox.pack_forget()

        # No changes to event bindings here, ensure image advancement works independently

    def toggle_feather_radius(self):
        if self.smoothing_var.get():
            self.feather_radius_label.pack(pady=5)
            self.feather_radius_entry.pack(pady=5)
        else:
            self.feather_radius_label.pack_forget()
            self.feather_radius_entry.pack_forget()

    def adjust_canvas_zoom(self):
        zoom = self.canvas_zoom.get()
        if zoom < 20:
            zoom = 20
        elif zoom > 80:
            zoom = 80
        self.canvas_zoom.set(zoom)
        self.max_canvas_size = self.calculate_canvas_size()
        self.canvas.config(width=self.max_canvas_size[0], height=self.max_canvas_size[1])
        self.update_idletasks()
        self.load_image()

    def select_directory(self):
        directory = filedialog.askdirectory()
        if directory:
            self.curr_dir.set(directory)
            self.calculate_max_image_number()  # New method to calculate max image number
            self.load_image()

    def calculate_max_image_number(self):
        # Get all image files in the selected directory
        all_files = [f for f in os.listdir(self.curr_dir.get()) if f.endswith('.png')]
        if not all_files:
            messagebox.showerror("Error", "No images found in the directory.")
            return

        # Convert filenames to integers and find the max image number
        self.images = sorted([int(os.path.splitext(f)[0]) for f in all_files])
        if self.images:
            self.max_image_number = max(self.images)
            self.update_image_num_label()  # Update the label and progress bar

    def load_image(self):
        image_number = self.current_image_number.get()
        merged_image_path = os.path.join(self.curr_dir.get(), f"{str(image_number).zfill(5)}.png")
        original_image_path = os.path.join(os.path.dirname(self.curr_dir.get()), f"{str(image_number).zfill(5)}.png")

        # Always load the images
        if os.path.isfile(merged_image_path):
            self.modified_image = Image.open(merged_image_path)
        else:
            messagebox.showerror("Error", f"Merged image {merged_image_path} not found.")
            return

        if os.path.isfile(original_image_path):
            self.data_dst_image = Image.open(original_image_path)
        else:
            messagebox.showerror("Error", f"Original image {original_image_path} not found.")
            return

        # Display the correct image based on the current selection
        if self.current_image == "Original Image" and self.data_dst_image:
            self.display_image(self.data_dst_image)
        elif self.modified_image:
            self.display_image(self.modified_image)

        self.update_image_num_label()  # Update label and progress bar when an image is loaded

        # Show or hide the tools based on the checkbox
        if self.keep_tools_visible_var.get():
            self.toggle_right_frame_controls(True)
        else:
            self.toggle_right_frame_controls(False)

    def update_image_num_label(self):
        # Update the image number label
        self.image_num_label.config(text=f"{self.current_image_number.get()}/{self.max_image_number}")

        # Update the progress bar
        progress = (self.current_image_number.get() / self.max_image_number) * 100
        self.progress_bar['value'] = progress

    def process_image(self):
        # Load both merged and original images into memory
        image_number = self.current_image_number.get()
        merged_image_path = os.path.join(self.curr_dir.get(), f"{str(image_number).zfill(5)}.png")
        original_image_path = os.path.join(os.path.dirname(self.curr_dir.get()), f"{str(image_number).zfill(5)}.png")

        if os.path.isfile(merged_image_path) and os.path.isfile(original_image_path):
            self.modified_image = Image.open(merged_image_path)
            self.data_dst_image = Image.open(original_image_path)
            self.display_image(self.modified_image)  # Default to showing the merged image

            # Show the additional controls
            self.toggle_right_frame_controls(True)
        else:
            messagebox.showerror("Error", "One or both images not found.")

    def update_displayed_image(self, event=None):
        if self.image_selector.get() == "Merged Image":
            self.current_image = "Merged Image"
            self.display_image(self.modified_image)
        elif self.image_selector.get() == "Original Image":
            self.current_image = "Original Image"
            self.display_image(self.data_dst_image)

    def display_image(self, image):
        if self.is_zoomed and self.zoomed_region:
            cropped_image = image.crop(self.zoomed_region)
            self.show_image(cropped_image)
        else:
            self.show_image(image)

    def show_image(self, image):
        img_width, img_height = image.size
        self.scale_factor = min(self.max_canvas_size[0] / img_width, self.max_canvas_size[1] / img_height)
        new_size = (int(img_width * self.scale_factor), int(img_height * self.scale_factor))
        resized_image = image.resize(new_size, Image.Resampling.LANCZOS)

        self.curr_image = ImageTk.PhotoImage(resized_image)
        self.canvas.create_image(0, 0, anchor=tk.NW, image=self.curr_image)
        self.canvas.config(scrollregion=self.canvas.bbox(tk.ALL))

    def start_zoom_mode(self):
        self.canvas.bind("<Button-1>", self.start_zoom_rect)
        self.canvas.bind("<B1-Motion>", self.draw_zoom_rect)
        self.canvas.bind("<ButtonRelease-1>", self.finish_zoom_rect)

    def start_zoom_rect(self, event):
        if self.zoom_rect:
            self.canvas.delete(self.zoom_rect)
        self.start_x = event.x
        self.start_y = event.y
        self.zoom_rect = self.canvas.create_rectangle(self.start_x, self.start_y, self.start_x, self.start_y,
                                                      outline='red')

    def draw_zoom_rect(self, event):
        current_x, current_y = event.x, event.y
        self.canvas.coords(self.zoom_rect, self.start_x, self.start_y, current_x, current_y)

    def finish_zoom_rect(self, event):
        self.end_x, self.end_y = event.x, event.y
        # Ensure the coordinates are in the correct order
        x1, y1 = min(self.start_x, self.end_x), min(self.start_y, self.end_y)
        x2, y2 = max(self.start_x, self.end_x), max(self.start_y, self.end_y)

        # Scale the coordinates back to the original image size
        x1_scaled = int(x1 / self.scale_factor)
        y1_scaled = int(y1 / self.scale_factor)
        x2_scaled = int(x2 / self.scale_factor)
        y2_scaled = int(y2 / self.scale_factor)

        # Define the zoomed region on the original image
        self.zoomed_region = (x1_scaled, y1_scaled, x2_scaled, y2_scaled)

        self.is_zoomed = True
        self.canvas.delete(self.zoom_rect)  # Remove the rectangle outline after zooming

        # Display the correct image based on the current selection
        if self.current_image == "Original Image":
            self.display_image(self.data_dst_image)
        else:
            self.display_image(self.modified_image)

        # Unbind zoom-related events
        self.canvas.unbind("<Button-1>")
        self.canvas.unbind("<B1-Motion>")
        self.canvas.unbind("<ButtonRelease-1>")

    def reset_zoom(self):
        self.is_zoomed = False
        self.zoomed_region = None

        # Determine the current image displayed on the canvas and reset the zoom accordingly
        if self.current_image == "Original Image":
            self.display_image(self.data_dst_image)
            self.image_selector.set("Original Image")
        elif self.current_image == "Merged Image":
            self.display_image(self.modified_image)
            self.image_selector.set("Merged Image")

        # Unbind zoom-related events
        self.canvas.unbind("<Button-1>")
        self.canvas.unbind("<B1-Motion>")
        self.canvas.unbind("<ButtonRelease-1>")

    def start_trace_mode(self):
        self.canvas.bind("<Button-1>", self.start_trace)
        self.canvas.bind("<B1-Motion>", self.draw_trace_path)
        self.canvas.bind("<ButtonRelease-1>", self.finish_trace)
        self.bind("<Escape>", self.clear_traced_path)  # Bind Esc key to clear the path

    def start_trace(self, event):
        self.traced_path = [(event.x, event.y)]
        self.trace_line_ids.append(
            self.canvas.create_oval(event.x - 5, event.y - 5, event.x + 5, event.y + 5, fill='red'))
        self.trace_line_ids.append(self.canvas.create_line(event.x, event.y, event.x, event.y, fill='blue'))

    def draw_trace_path(self, event):
        # Add the new point to the traced path
        self.traced_path.append((event.x, event.y))

        # Draw the line segment connecting the previous point to the new point
        if len(self.traced_path) > 1:
            line_id = self.canvas.create_line(self.traced_path[-2], self.traced_path[-1], fill='blue')
            self.trace_line_ids.append(line_id)

    def clear_traced_path(self, event=None):
        # Delete all lines and ovals associated with the traced path
        for line_id in self.trace_line_ids:
            self.canvas.delete(line_id)
        # Clear the traced path and line IDs
        self.traced_path.clear()
        self.trace_line_ids.clear()

    def flatten_coords(self, coords):
        return [coord for xy in coords for coord in xy]

    def finish_trace(self, event):
        if self.is_zoomed:
            self.finish_trace_zoomed(event)
        else:
            self.finish_trace_unzoomed(event)

    def finish_trace_unzoomed(self, event):
        self.traced_path.append(self.traced_path[0])  # Close the path

        # Clear existing lines to prevent overlap
        for line_id in self.trace_line_ids:
            self.canvas.delete(line_id)
        self.trace_line_ids.clear()

        # Draw the actual trace in blue
        for i in range(len(self.traced_path) - 1):
            line_id = self.canvas.create_line(self.traced_path[i], self.traced_path[i + 1], fill='blue')
            self.trace_line_ids.append(line_id)

        # Highlight the path in yellow
        self.highlight_traced_path_unzoomed()

    def finish_trace_zoomed(self, event):
        self.traced_path.append(self.traced_path[0])  # Close the path

        # Adjust the trace for zoomed mode
        adjusted_path = []
        for x, y in self.traced_path:
            x_adj = int((x / self.scale_factor) + self.zoomed_region[0])
            y_adj = int((y / self.scale_factor) + self.zoomed_region[1])
            adjusted_path.append((x_adj, y_adj))
        self.traced_path = adjusted_path

        # Clear existing lines to prevent overlap
        for line_id in self.trace_line_ids:
            self.canvas.delete(line_id)
        self.trace_line_ids.clear()

        # Draw the actual trace in blue
        for i in range(len(self.traced_path) - 1):
            line_id = self.canvas.create_line(self.traced_path[i], self.traced_path[i + 1], fill='blue')
            self.trace_line_ids.append(line_id)

        # Highlight the path in yellow
        self.highlight_traced_path_zoomed()

    def highlight_traced_path_unzoomed(self):
        # Use the same coordinates as the blue path to draw the yellow line
        for i in range(len(self.traced_path) - 1):
            line_id = self.canvas.create_line(
                self.traced_path[i], self.traced_path[i + 1],
                fill='yellow', width=2
            )
            self.trace_line_ids.append(line_id)

    def highlight_traced_path_zoomed(self):
        # Clear any previous yellow lines to prevent overlap
        for line_id in self.trace_line_ids:
            self.canvas.delete(line_id)

        self.trace_line_ids.clear()

        # Adjust and draw the yellow line with more precision
        for i in range(len(self.traced_path) - 1):
            x1, y1 = self.traced_path[i]
            x2, y2 = self.traced_path[i + 1]

            # Instead of scaling manually, rely on the original tracing data for precision
            x1_scaled = int((x1 - self.zoomed_region[0]) * self.scale_factor)
            y1_scaled = int((y1 - self.zoomed_region[1]) * self.scale_factor)
            x2_scaled = int((x2 - self.zoomed_region[0]) * self.scale_factor)
            y2_scaled = int((y2 - self.zoomed_region[1]) * self.scale_factor)

            # Draw the yellow line with more accurate scaling
            line_id = self.canvas.create_line(x1_scaled, y1_scaled, x2_scaled, y2_scaled, fill='yellow', width=2)
            self.trace_line_ids.append(line_id)

    def copy_traced_area(self):
        if self.is_zoomed:
            self.copy_traced_area_zoomed()
        else:
            self.copy_traced_area_unzoomed()

        # After copying, ensure that the merged image is set as the current image
        self.current_image = "Merged Image"
        self.image_selector.set("Merged Image")

    def copy_traced_area_unzoomed(self):
        if self.data_dst_image and self.traced_path:
            self.previous_image_state = self.modified_image.copy()  # Save current state for undo
            mask = Image.new("L", self.modified_image.size, 0)
            draw = ImageDraw.Draw(mask)

            # Use the original traced path (blue line) for copying
            scaled_traced_path = [(int(x / self.scale_factor), int(y / self.scale_factor)) for x, y in self.traced_path]
            draw.polygon(scaled_traced_path, outline=1, fill=255)

            selected_area = Image.new("RGB", self.modified_image.size)
            selected_area.paste(self.data_dst_image, mask=mask)
            self.modified_image.paste(selected_area, mask=mask)

            # After copying, display the modified image and update dropdown to reflect the change
            self.display_image(self.modified_image)
            self.image_selector.set("Merged Image")
            self.clear_traced_path()  # Clear the path after copying

    def copy_traced_area_zoomed(self):
        if self.data_dst_image and self.traced_path:
            self.previous_image_state = self.modified_image.copy()  # Save current state for undo
            mask = Image.new("L", self.modified_image.size, 0)
            draw = ImageDraw.Draw(mask)

            # Use the original traced path (blue line) for copying
            draw.polygon(self.traced_path, outline=1, fill=255)

            selected_area = Image.new("RGB", self.modified_image.size)
            selected_area.paste(self.data_dst_image, mask=mask)
            self.modified_image.paste(selected_area, mask=mask)

            # After copying, display the modified image and update dropdown to reflect the change
            self.display_image(self.modified_image)
            self.image_selector.set("Merged Image")
            self.clear_traced_path()  # Clear the path after copying

    def apply_smoothing(self, image, mask):
        # Feather the mask by applying a slight blur to it
        feather_radius = self.feather_radius.get()  # Use the user-defined feather radius
        feathered_mask = mask.filter(ImageFilter.GaussianBlur(radius=feather_radius))

        # Create an image for blending where the original image is at the boundaries
        blended_image = Image.composite(image, self.previous_image_state, feathered_mask)

        # Blend the feathered boundary back into the original image
        smoothed_image = Image.composite(blended_image, image, feathered_mask)

        return smoothed_image

    def undo_last_action(self):
        if self.previous_image_state:
            self.modified_image = self.previous_image_state
            self.display_image(self.modified_image)
            self.previous_image_state = None  # Clear undo history after undoing

    def save_image(self):
        if self.modified_image:
            save_path = os.path.join(self.curr_dir.get(), f"{str(self.current_image_number.get()).zfill(5)}.png")
            if self.backup_var.get():  # If backup is checked
                backup_path = save_path + ".bak"
                if os.path.isfile(save_path):
                    os.rename(save_path, backup_path)  # Rename the old file to create a backup
            self.modified_image.save(save_path)
            print(f"Image saved to {save_path}")  # Print save message to console
            self.load_image()  # Reload the saved image to show it
            self.toggle_right_frame_controls(False)  # Hide controls after saving

    def flatten_coords(self, coords):
        return [coord for xy in coords for coord in xy]

    def start_next_image_loop(self, event):
        self.is_advancing = True
        self.advance_images("next")

    def start_previous_image_loop(self, event):
        self.is_advancing = True
        self.advance_images("previous")

    def stop_image_loop(self, event=None):
        self.is_advancing = False

    def advance_images(self, direction):
        if self.is_advancing:
            if direction == "next":
                self.next_image()
            elif direction == "previous":
                self.previous_image()
            self.after(self.advance_delay.get(), lambda: self.advance_images(direction))

    def next_image(self):
        self.current_image_number.set(self.current_image_number.get() + 1)
        self.load_image()

    def previous_image(self):
        if self.current_image_number.get() > 1:
            self.current_image_number.set(self.current_image_number.get() - 1)
            self.load_image()

    def update_speed(self):
        delay = self.advance_delay.get()
        if delay < 1:  # Set a lower limit to avoid too fast advancement
            self.advance_delay.set(1)
        elif delay > 1000:  # Set an upper limit for the delay
            self.advance_delay.set(1000)

    def use_original_image(self):
        image_number = self.current_image_number.get()
        merged_image_path = os.path.join(self.curr_dir.get(), f"{str(image_number).zfill(5)}.png")
        original_image_path = os.path.join(os.path.dirname(self.curr_dir.get()), f"{str(image_number).zfill(5)}.png")

        if os.path.isfile(original_image_path):
            # Optionally make a backup
            if self.use_original_backup_var.get() and os.path.isfile(merged_image_path):
                backup_path = merged_image_path + ".bak"
                os.rename(merged_image_path, backup_path)

            # Copy the original image to the merged directory
            self.data_dst_image.save(merged_image_path)
            print(f"Copied original image to {merged_image_path}")

            # Advance to the next image
            self.next_image()

            # Load images for the next image if tools are kept visible
            if self.keep_tools_visible_var.get():
                self.load_image()

        else:
            messagebox.showerror("Error", f"Original image {original_image_path} not found.")


if __name__ == "__main__":
    app = ImageProcessorApp()
    app.mainloop()
