// Build from openFoam/: c++ -std=c++17 -Wall -Wextra -Wpedantic new_run.cpp -o new_run
// Execute: ./new_run
// Edit RUN_NAME below and rebuild to make a differently named run.

#include <algorithm>
#include <cctype>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <iterator>
#include <stdexcept>
#include <string>
#include <system_error>
#include <vector>

namespace fs = std::filesystem;

// -------------------- EDIT THESE SETTINGS --------------------
const std::string RUN_NAME = "run1"; // "run 1" is also allowed.
constexpr int CPU_CORES = 1;          // 1 = serial; >1 = MPI parallel.
// ------------------------------------------------------------

// std::string, vector, path and file streams manage their own memory/resources
// (RAII). No manual new/delete is needed for a file-copying application.
bool valid_name(const std::string& name)
{
    if (name.empty() || !std::isalnum(static_cast<unsigned char>(name.front())) ||
        name.back() == ' ')
        return false;
    return std::all_of(name.begin(), name.end(), [](unsigned char character) {
        return std::isalnum(character) || character == '_' || character == '-' || character == ' ';
    });
}

// Find the workspace from its contents, so running the binary from another
// directory still works. An optional workspace argument is useful for testing.
fs::path find_workspace(int argc, char* argv[])
{
    std::vector<fs::path> candidates;
    if (argc == 2)
        candidates.emplace_back(argv[1]);
    else
        candidates = {fs::current_path(), fs::current_path() / "openFoam",
                      fs::absolute(argv[0]).parent_path()};
    for (const auto& candidate : candidates) {
        if (fs::is_directory(candidate / "templates/05_incompressible_stl") &&
            fs::is_regular_file(candidate / "scripts/run_geometry.sh"))
            return fs::canonical(candidate);
    }
    throw std::runtime_error("OpenFOAM workspace not found. Run from openFoam/ or pass its path.");
}

void write_text(const fs::path& file, const std::string& contents)
{
    // The stream closes automatically when this function exits, even on errors.
    std::ofstream output(file);
    output.exceptions(std::ios::failbit | std::ios::badbit);
    output << contents;
}

void set_core_count(const fs::path& dictionary)
{
    std::ifstream input(dictionary);
    if (!input)
        throw std::runtime_error("Cannot read " + dictionary.string());
    std::string contents{std::istreambuf_iterator<char>(input), {}};
    const std::string original = "numberOfSubdomains 1;";
    const auto position = contents.find(original);
    if (position == std::string::npos)
        throw std::runtime_error("Expected numberOfSubdomains 1; in the CAD template.");
    contents.replace(position, original.size(), "numberOfSubdomains " + std::to_string(CPU_CORES) + ";");
    input.close();
    write_text(dictionary, contents);
}

void make_executable(const fs::path& script)
{
    fs::permissions(script, fs::perms::owner_exec | fs::perms::group_exec | fs::perms::others_exec,
                    fs::perm_options::add);
}

int main(int argc, char* argv[])
{
    fs::path destination;
    bool created = false;
    try {
        if (argc > 2)
            throw std::runtime_error("Usage: ./new_run [path-to-openFoam-workspace]");
        if (!valid_name(RUN_NAME))
            throw std::runtime_error("RUN_NAME must start with a letter/digit and contain only letters, digits, spaces, _ or - (no trailing space).");
        if (CPU_CORES < 1)
            throw std::runtime_error("CPU_CORES must be at least 1.");

        const auto workspace = find_workspace(argc, argv);
        const auto source = workspace / "templates/05_incompressible_stl";
        const auto runs = workspace / "runs";
        if (fs::is_symlink(runs))
            throw std::runtime_error("runs/ must be a real directory, not a symbolic link.");
        destination = runs / RUN_NAME;

        // Refuse existing runs: your edits and results must never be overwritten.
        if (fs::exists(destination) || fs::is_symlink(destination))
            throw std::runtime_error("Run already exists: " + destination.string() +
                                     "\nRename RUN_NAME and rebuild, or manually delete that run first.");

        // Explicit input list: don't copy accidental geometry, logs or old results
        // that someone may have dropped in a reference template.
        const std::vector<fs::path> inputs = {
            "0/U", "0/p", "constant/transportProperties", "constant/turbulenceProperties",
            "system/blockMeshDict", "system/snappyHexMeshDict", "system/surfaceFeatureExtractDict",
            "system/controlDict", "system/fvSchemes", "system/fvSolution",
            "system/decomposeParDict", "README.md"
        };
        for (const auto& relative : inputs)
            if (!fs::is_regular_file(source / relative))
                throw std::runtime_error("Missing template input: " + (source / relative).string());
        for (const auto& helper : {"run_case.sh", "run_geometry.sh"})
            if (!fs::is_regular_file(workspace / "scripts" / helper))
                throw std::runtime_error(std::string("Missing helper: ") + helper);

        fs::create_directories(runs);
        // create_directory reserves our destination; a simultaneous invocation
        // cannot claim the same run and copy over our files.
        if (!fs::create_directory(destination))
            throw std::runtime_error("Run directory was just created by another process; nothing overwritten.");
        created = true;
        for (const auto& relative : inputs) {
            fs::create_directories((destination / relative).parent_path());
            fs::copy_file(source / relative, destination / relative);
        }
        fs::create_directories(destination / "constant/triSurface");
        fs::copy_file(workspace / "scripts/run_geometry.sh", destination / "Allrun");
        fs::copy_file(workspace / "scripts/run_case.sh", destination / "run_case.sh");
        make_executable(destination / "Allrun");
        make_executable(destination / "run_case.sh");
        set_core_count(destination / "system/decomposeParDict");

        std::cout << "Created " << destination << '\n'
                  << "1. Drop one STL or STEP file directly into this run folder.\n"
                  << "2. Edit the copied inputs for your geometry, units and fluid (see its README.md).\n"
                  << "3. Open a terminal there: ./Allrun --mesh-only\n"
                  << "4. Inspect case.foam, then: ./Allrun --existing-mesh\n"
                  << "Delete only this run folder and execute the generator again for a fresh copy.\n";
    } catch (const std::exception& error) {
        // Roll back only a directory created by THIS invocation. A pre-existing
        // run is never cleaned or deleted by the generator.
        if (created) {
            std::error_code cleanup_error;
            fs::remove_all(destination, cleanup_error);
            if (cleanup_error)
                std::cerr << "Incomplete run remains at " << destination << '\n';
        }
        std::cerr << "Error: " << error.what() << '\n';
        return 1;
    }
    return 0;
}
