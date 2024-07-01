import tkinter as tk
from PIL import Image, ImageTk


def show_image_after_delay(image_path, delay, display_time):
    root = tk.Tk()
    root.withdraw()  # Hide the main window initially

    def close_window():
        root.destroy()  # Close the window

    def display_image():
        root.deiconify()  # Show the main window
        root.attributes('-topmost', True)  # Make the window topmost

        # Get screen width and height
        screen_width = root.winfo_screenwidth()
        screen_height = root.winfo_screenheight()

        # Load the image
        img = Image.open(image_path)

        # Calculate the target size for the image (covering half of the screen)
        target_width = screen_width * 5 // 6
        target_height = screen_height * 5 // 6

        # Calculate the scaling factor to maintain the aspect ratio
        scale_factor = min(target_width / img.width, target_height / img.height)

        # Apply the scaling factor
        new_width = int(img.width * scale_factor)
        new_height = int(img.height * scale_factor)

        # Resize the image
        img = img.resize((new_width, new_height), Image.LANCZOS)
        img = ImageTk.PhotoImage(img)

        # Create a panel to display the image
        panel = tk.Label(root, image=img)
        panel.image = img  # Keep a reference to avoid garbage collection
        panel.pack(expand=True)

        # Adjust the window size to fit the image
        root.geometry(f"{new_width}x{new_height}+{(screen_width - new_width) // 2}+{(screen_height - new_height) // 2}")

        # Close the window after the display time
        root.after(display_time, close_window)

    root.after(delay, display_image)  # Call display_image after delay
    root.mainloop()


if __name__ == "__main__":
    image_path = r"C:\Users\Zhouyuan\Pictures\fanqie\1.png"  # Replace with your image path
    delay = 15 * 60 * 1000  # 15 minutes in milliseconds
    delay_time = 5 * 60 * 1000
    show_image_after_delay(image_path, delay,delay_time)
