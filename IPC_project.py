import os
import random
import multiprocessing.shared_memory as shared_memory
import time

#The number of child processes

NUM_CHILDREN = 4

#First we define the child process
def child_process(pipe_write_end):
    """Function executed by each child process."""
    #We generate a random int between 0-19
    rand_num = random.randint(0, 19)
    print(f"Child {os.getpid()} generated: {rand_num}")

    #Then we send the random number to the parent process through the pipe
    os.write(pipe_write_end, rand_num.to_bytes(4, 'little'))

    #We close the write end of the pipe after the data has been sent
    os.close(pipe_write_end)


#Then we define the parent process
def parent_process(pipe_read_ends, shm_name):
    """Function executed by the parent process (init)."""

#We create a list to store the random numbers from each child
random_numbers = []

#We read the random numberts from all child processes via the pipes
for i in range(NUM_CHILDREN):
    data = os.read(pipe_read_ends[i], 4)
    rand_num = int.from_bytes(data, 'little')
    print(f"Parent received from child {i+1}: {rand_num}")
    random_numbers.append(rand_num)

#Then we attach the shard memory created by the scheduler process
shm = shared_memory.SharedMemory(name=shm_name)
#And then copy the random number to the shared memory
for i, num in enumerate(random_numbers):
    shm.buf[i*4:i*4+4] = num.to_bytes(4, 'little')

#And then we close the shared memory
shm.close()

#Then we define the scheduler process
def scheduler_process():
    """Function executed by the scheduler process."""
    #We create a shared memory segment that can hold 4 integers (4 bytes per int)
    shm = shared_memory.SharedMemory(create=True, size=NUM_CHILDREN * 4)
    print(f"Scheduler created shared memory: {shm.name}")

    #We wait for the parent process (init) to write data into shared memory
    time.sleep(2) #This creates some delay for the parent to write

    #After that we read the numbers from shared memory
    random_numbers = [int.from_bytes(shm.buf[i*4:i*4+4], 'little') for i in range(NUM_CHILDREN)]
    print(f"Scheduler read from the shared memory: {random_numbers}")

    #We sort the numbers
    random_numbers.sort()
    print(f"Scheduler sorted numbers: {random_numbers}")

    #We "clean up" as we detach and delete the shared memory segment
    shm.close()
    shm.unlink() #This removes the shared memory segment from the system

if __name__ == "__main__":
    #Lets create the pipes for parent-child communication
    pipes = [os.pipe() for _ in range(NUM_CHILDREN)]

    #Fork child processes
    for i in range(NUM_CHILDREN):
        pid = os.fork()
        if pid == 0: #Child process
            #Close the read end of the pipe and run the child process function
            os.close(pipes[i][0])
            child_process(pipes[i][1])
            os._exit(0) #Exit the child process after sending the data

    #Only the parent process should reach this point
    #We close the write end sof all pipes in the parent
    for i in range(NUM_CHILDREN):
        os.close(pipes[i][1])

    #Fork the scheduler process
    scheduler_pid = os.fork()
    if scheduler_pid == 0: # Scheduler process
        scheduler_process()
        os._exit(0) #We exit the scheduler process after sorting

    #Parent process (init)
    #We need to wait a moment to allow the schedulder to create shared memory
    time.sleep(1)

    #We run the parent process function, passing the read ends of pipes and the shared memory name
    parent_process([pipes[i][0] for i in range(NUM_CHILDREN)], shm_name="psm")

    #And lastly we wait for the scheduler to finish
    os.waitpid(scheduler_pid, 0)
    print("All processses complete.")