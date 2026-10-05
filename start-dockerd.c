/* start-dockerd: setuid-root wrapper so an unprivileged evaluation can start
 * the Docker daemon inside the (privileged) autograder container.
 *
 * Making /usr/bin/dockerd itself setuid does not work: the daemon then runs
 * with effective uid 0 but real uid of the caller, and the helpers it execs
 * (iptables in particular) refuse that half-privileged state. This wrapper
 * becomes root outright, then execs dockerd with the caller's arguments.
 *
 * Installed as /usr/local/bin/start-dockerd, mode 4755. The daemon still needs
 * the container to run with --privileged; a codeval file that needs Docker
 * starts it with:
 *   CMD start-dockerd >/tmp/dockerd.log 2>&1 & for i in $(seq 1 30); do docker info >/dev/null 2>&1 && break; sleep 1; done
 */
#include <stdio.h>
#include <unistd.h>

int main(int argc, char **argv) {
    (void)argc;
    if (setresgid(0, 0, 0) != 0 || setresuid(0, 0, 0) != 0) {
        perror("start-dockerd: cannot become root (is the binary setuid root?)");
        return 1;
    }
    argv[0] = "dockerd";
    execv("/usr/bin/dockerd", argv);
    perror("start-dockerd: exec /usr/bin/dockerd");
    return 1;
}
