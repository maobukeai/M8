import bpy


def debounce(wait):
    """Run the final call on Blender's main thread after a quiet interval."""

    def decorator(func):
        generation = 0

        def debounced(*args, **kwargs):
            nonlocal generation
            generation += 1
            current_generation = generation

            def run_on_main_thread():
                if current_generation == generation:
                    func(*args, **kwargs)
                return None

            bpy.app.timers.register(run_on_main_thread, first_interval=wait)

        return debounced

    return decorator
