import os
import random
import multiprocessing.shared_memory as shared_memory
import time

# Number of child processes
NUM_CHILDREN = 4

def child_process(pipe_write_end):
    """Function executed by each child process."""
    # Generate a random integer between 0-19
    rand_num = random.randint(0, 19)
    print(f"Child {os.getpid()} generated: {rand_num}")
    
    # Send the random number to the parent process through the pipe
    os.write(pipe_write_end, rand_num.to_bytes(4, 'little'))
    
    # Close the write end of the pipe after sending data
    os.close(pipe_write_end)

def parent_process(pipe_read_ends, shm_pipe_read):
    """Function executed by the parent process (init)."""
    # List to store the random numbers from each child
    random_numbers = []

    # Read random numbers from all child processes via the pipes
    for i in range(NUM_CHILDREN):
        data = os.read(pipe_read_ends[i], 4)
        rand_num = int.from_bytes(data, 'little')
        print(f"Parent received from child {i+1}: {rand_num}")
        random_numbers.append(rand_num)
    
    # Wait to receive the shared memory name from the scheduler
    shm_name_bytes = os.read(shm_pipe_read, 128)
    shm_name = shm_name_bytes.decode().strip('\x00')
    print(f"Parent received shared memory name: {shm_name}")

    # Attach to the shared memory created by the scheduler process
    shm = shared_memory.SharedMemory(name=shm_name)
    
    # Copy the random numbers to the shared memory
    for i, num in enumerate(random_numbers):
        shm.buf[i*4:i*4+4] = num.to_bytes(4, 'little')

    # Detach from shared memory (shm.close only closes the handle, not the memory itself)
    shm.close()

def scheduler_process(shm_pipe_write):
    """Function executed by the scheduler process."""
    # Create a shared memory segment that can hold 4 integers (4 bytes per int)
    shm = shared_memory.SharedMemory(create=True, size=NUM_CHILDREN * 4)
    print(f"Scheduler created shared memory: {shm.name}")

    # Send the shared memory name to the parent process
    os.write(shm_pipe_write, shm.name.encode())

    # Wait for the parent process (init) to write data into shared memory
    time.sleep(2)  # Simulate some delay for parent to write

    # Read the numbers from shared memory
    random_numbers = [int.from_bytes(shm.buf[i*4:i*4+4], 'little') for i in range(NUM_CHILDREN)]
    print(f"Scheduler read from shared memory: {random_numbers}")
    
    # Sort the numbers
    random_numbers.sort()
    print(f"Scheduler sorted numbers: {random_numbers}")
    
    # Clean up: Detach the shared memory segment, but don't unlink it yet
    shm.close()
    
    return shm.name  # Return the name of the shared memory to be unlinked later

if __name__ == "__main__":
    # Create pipes for parent-child communication
    pipes = [os.pipe() for _ in range(NUM_CHILDREN)]
    
    # Create a pipe for scheduler to parent communication (shared memory name)
    shm_pipe = os.pipe()

    # Fork child processes
    for i in range(NUM_CHILDREN):
        pid = os.fork()
        if pid == 0:  # Child process
            # Close the read end of the pipe and run the child process function
            os.close(pipes[i][0])
            child_process(pipes[i][1])
            os._exit(0)  # Exit child process after sending data
    
    # Only the parent reaches this point
    # Close the write ends of all pipes in the parent
    for i in range(NUM_CHILDREN):
        os.close(pipes[i][1])
    
    # Fork the scheduler process
    scheduler_pid = os.fork()
    if scheduler_pid == 0:  # Scheduler process
        # Close the read end of the shm_pipe in scheduler
        os.close(shm_pipe[0])
        shm_name = scheduler_process(shm_pipe[1])
        os._exit(0)  # Exit scheduler process after sorting

    # Parent process (init)
    # Close the write end of the shm_pipe in parent
    os.close(shm_pipe[1])

    # Run the parent process function, passing the read ends of the pipes and the shared memory pipe
    parent_process([pipes[i][0] for i in range(NUM_CHILDREN)], shm_pipe[0])

    # Wait for the scheduler to finish
    os.waitpid(scheduler_pid, 0)
    
    # Now that all processes are done, we can safely unlink the shared memory
    shm = shared_memory.SharedMemory(name=shm_name)
    shm.unlink()  # This removes the shared memory segment from the system
    print("All processes complete and shared memory unlinked.")
