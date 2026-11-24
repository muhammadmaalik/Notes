// A case manager, not a CFD solver. OpenFOAM solves the copied dictionaries.
#include <filesystem>
#include <fstream>
#include <iostream>
#include <regex>
#include <stdexcept>
#include <string>
#include <vector>
#include <cerrno>
#include <sys/wait.h>
#include <unistd.h>

namespace fs = std::filesystem;
struct Template { std::string name, solver, description; };
const std::vector<Template> templates = {
    {"cavity", "icoFoam", "2D transient laminar lid-driven cavity (Re=100)"},
    {"incomp", "simpleFoam", "3D steady laminar channel"},
    {"transient", "pimpleFoam", "3D transient laminar channel"},
    {"external-stl", "simpleFoam", "3D steady k-omega SST flow around a closed STL body"}
};

int execute(const std::vector<std::string>& args) {
    std::vector<char*> argv;
    for (const auto& arg : args) argv.push_back(const_cast<char*>(arg.c_str()));
    argv.push_back(nullptr);
    const pid_t child = fork();
    if (child < 0) throw std::runtime_error("Cannot start child process");
    if (child == 0) {
        execv(argv[0], argv.data());
        perror("execv");
        _exit(127);
    }
    int status = 0;
    while (waitpid(child, &status, 0) < 0) {
        if (errno != EINTR) throw std::runtime_error("Cannot wait for child process");
    }
    return WIFEXITED(status) ? WEXITSTATUS(status) : 128 + WTERMSIG(status);
}

void validateName(const std::string& name) {
    if (!std::regex_match(name, std::regex("[A-Za-z0-9][A-Za-z0-9_-]*")))
        throw std::runtime_error("Use a run name containing letters, digits, _ or - (no paths).");
}

void help() {
    std::cout << R"(Usage: ./scripts/foam COMMAND
  list                              Show available simulation templates
  new TYPE [NAME]                    Copy a complete case to runs/NAME
                                    Default name: next unused run1, run2, ...
  mesh NAME                         Generate and check a new mesh
  remesh NAME                       Rebuild mesh before any results exist
  check NAME                        Check an existing mesh
  run NAME [--parallel N]            Mesh if needed, check, then solve
  solve NAME [--parallel N]          Check and solve an existing mesh
  view NAME                         Open the case in host ParaView
  doctor                            Report runtime and verify OpenFOAM version

Examples:
  ./scripts/foam new incomp
  ./scripts/foam new external-stl wing
  ./scripts/import_geometry.sh wing /path/to/wing.stl --scale 0.001
  ./scripts/foam run wing

Edit runs/NAME/{0,constant,system} before running. See README.md and docs/geometry.md.
)";
}

int main(int argc, char** argv) {
    try {
        const fs::path root = fs::canonical("/proc/self/exe").parent_path().parent_path();
        if (argc < 2 || std::string(argv[1]) == "--help" || std::string(argv[1]) == "help") {
            help(); return 0;
        }
        const std::string command = argv[1];
        if (command == "list" && argc == 2) {
            for (const auto& item : templates)
                std::cout << item.name << " (" << item.solver << "): " << item.description << '\n';
            return 0;
        }
        if (command == "doctor" && argc == 2)
            return execute({(root / "scripts/doctor.sh").string()});
        if (command == "new" && (argc == 3 || argc == 4)) {
            const std::string type = argv[2];
            bool known = false;
            for (const auto& item : templates) if (item.name == type) known = true;
            if (!known) throw std::runtime_error("Unknown simulation type. Use: ./scripts/foam list");
            fs::create_directories(root / "runs");
            std::string name;
            if (argc == 4) name = argv[3];
            else {
                unsigned index = 1;
                do { name = "run" + std::to_string(index++); } while (fs::exists(root / "runs" / name));
            }
            validateName(name);
            const fs::path target = root / "runs" / name;
            if (fs::exists(target) || fs::is_symlink(target))
                throw std::runtime_error("Run already exists; choose a new name. No files were overwritten.");
            // Reserve the destination so concurrent invocations cannot merge cases.
            if (!fs::create_directory(target)) throw std::runtime_error("Could not reserve run directory");
            try {
                fs::copy(root / "templates" / type, target, fs::copy_options::recursive);
                fs::copy_file(root / "scripts/Allrun", target / "Allrun");
                fs::permissions(target / "Allrun", fs::perms::owner_exec | fs::perms::group_exec |
                                fs::perms::others_exec, fs::perm_options::add);
                std::ofstream marker(target / "case.foam");
            } catch (...) { fs::remove_all(target); throw; }
            std::cout << "Created " << target << "\nEdit 0/, constant/, and system/, then:\n"
                      << "  ./scripts/foam run " << name << '\n';
            return 0;
        }
        if ((command == "mesh" || command == "remesh" || command == "check" || command == "run" || command == "solve" || command == "view") && argc >= 3) {
            validateName(argv[2]);
            std::vector<std::string> args{(root / "scripts/run_case.sh").string(), argv[2], command};
            for (int i = 3; i < argc; ++i) args.emplace_back(argv[i]);
            return execute(args);
        }
        help();
        throw std::runtime_error("Invalid command or argument count");
    } catch (const std::exception& error) {
        std::cerr << "Error: " << error.what() << '\n';
        return 1;
    }
}
