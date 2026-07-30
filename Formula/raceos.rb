# Homebrew Formula — RaceOS AI Software Factory
#
# This formula is published to: https://github.com/raceos/homebrew-tap
#
# Users install via:
#   brew tap raceos/tap
#   brew install raceos
#
# This file is auto-updated by the release workflow when a new
# version is published to PyPI.

class Raceos < Formula
  include Language::Python::Virtualenv

  desc "AI Software Factory for the RaceOS motorsport platform"
  homepage "https://github.com/raceos/raceos-factory"
  url "https://files.pythonhosted.org/packages/source/r/raceos-factory/raceos_factory-1.0.0.tar.gz"
  sha256 "PLACEHOLDER_SHA256"
  license "MIT"

  depends_on "python@3.12"
  depends_on "node" => :recommended  # For MCP servers via npx

  def install
    virtualenv_install_with_resources
  end

  test do
    assert_match "raceos", shell_output("#{bin}/raceos --version")
  end
end
