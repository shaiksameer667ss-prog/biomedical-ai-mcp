import unittest
import test_agent_alignment

if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromModule(test_agent_alignment)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    raise SystemExit(0 if result.wasSuccessful() else 1)
