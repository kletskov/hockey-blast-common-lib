import time


class ProgressTracker:
    """
    Reusable progress tracker with ETA calculation for stats aggregation processes.
    Supports optional custom counters for tracking additional metrics.
    """

    def __init__(self, total_items, description="Processing", custom_counters=None):
        self.total_items = total_items
        self.description = description
        self.start_time = time.time()
        self.processed_items = 0
        self.last_update_time = self.start_time
        self.custom_counters = custom_counters if custom_counters else {}

    def update(self, processed_count=None, **kwargs):
        """
        Update progress. If processed_count is None, increment by 1.
        kwargs can be used to update custom counters.
        """
        if processed_count is not None:
            self.processed_items = processed_count
        else:
            self.processed_items += 1

        # Update custom counters
        for key, value in kwargs.items():
            if key in self.custom_counters:
                self.custom_counters[key] = value

        current_time = time.time()

        # Only update display if at least 0.1 seconds have passed (to avoid spamming)
        if (
            current_time - self.last_update_time >= 0.1
            or self.processed_items == self.total_items
        ):
            self._display_progress()
            self.last_update_time = current_time

    def _display_progress(self):
        """
        Display progress with percentage, ETA, and elapsed time.
        """
        current_time = time.time()
        elapsed_time = current_time - self.start_time

        if self.processed_items == 0:
            percentage = 0.0
            eta_str = "calculating..."
        else:
            percentage = (self.processed_items / self.total_items) * 100

            # Calculate ETA
            if self.processed_items == self.total_items:
                eta_str = "completed!"
            else:
                avg_time_per_item = elapsed_time / self.processed_items
                remaining_items = self.total_items - self.processed_items
                eta_seconds = avg_time_per_item * remaining_items
                eta_str = self._format_time(eta_seconds)

        elapsed_str = self._format_time(elapsed_time)

        progress_msg = f"\r{self.description}: {self.processed_items}/{self.total_items} ({percentage:.1f}%) | "
        progress_msg += f"Elapsed: {elapsed_str} | ETA: {eta_str}"

        # Add custom counters to the display
        if self.custom_counters:
            counter_parts = [
                f"{key}: {value}" for key, value in self.custom_counters.items()
            ]
            progress_msg += " | " + ", ".join(counter_parts)

        print(progress_msg, end="", flush=True)

        # Add newline when complete
        if self.processed_items == self.total_items:
            print()  # Newline to finish the progress line

    def _format_time(self, seconds):
        """
        Format seconds into a human-readable string.
        """
        if seconds < 60:
            return f"{seconds:.1f}s"
        elif seconds < 3600:
            minutes = int(seconds // 60)
            secs = int(seconds % 60)
            return f"{minutes}m {secs}s"
        else:
            hours = int(seconds // 3600)
            minutes = int((seconds % 3600) // 60)
            return f"{hours}h {minutes}m"

    def finish(self):
        """
        Mark progress as complete and add final newline.
        """
        self.processed_items = self.total_items
        self._display_progress()


def create_progress_tracker(
    total_items, description="Processing", custom_counters=None
):
    """
    Factory function to create a progress tracker.
    custom_counters: dict of counter_name: initial_value for additional metrics to track
    """
    return ProgressTracker(total_items, description, custom_counters)
