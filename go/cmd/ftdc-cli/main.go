package main

import (
	"context"
	"fmt"
	"os"

	"github.com/mongodb/ftdc"
	"github.com/spf13/cobra"
)

var (
	version = "0.1.0"
)

func main() {
	if err := rootCmd.Execute(); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}

var rootCmd = &cobra.Command{
	Use:   "ftdc-cli",
	Short: "MongoDB FTDC parser and analysis tool",
	Long: `ftdc-cli is a command-line tool for parsing and analyzing MongoDB FTDC files.
It provides commands to extract metrics, export to various formats, and verify FTDC data.`,
	Version: version,
}

var extractCmd = &cobra.Command{
	Use:   "extract [ftdc-file]",
	Short: "Extract metrics from FTDC file to CSV",
	Long:  `Extract metrics from an FTDC file and export to CSV format.`,
	Args:  cobra.ExactArgs(1),
	RunE:  runExtract,
}

var (
	outputFile string
	dumpPrefix string
)

func init() {
	rootCmd.AddCommand(extractCmd)

	extractCmd.Flags().StringVarP(&outputFile, "output", "o", "", "Output CSV file (default: stdout)")
	extractCmd.Flags().StringVar(&dumpPrefix, "dump-prefix", "", "Dump to multiple CSV files with this prefix (handles schema changes)")
}

func runExtract(cmd *cobra.Command, args []string) error {
	inputFile := args[0]

	// Open FTDC file
	f, err := os.Open(inputFile)
	if err != nil {
		return fmt.Errorf("failed to open FTDC file: %w", err)
	}
	defer f.Close()

	ctx := context.Background()

	// Use DumpCSV if prefix is provided (handles schema changes)
	if dumpPrefix != "" {
		iter := ftdc.ReadChunks(ctx, f)
		if err := ftdc.DumpCSV(ctx, iter, dumpPrefix); err != nil {
			return fmt.Errorf("failed to dump CSV: %w", err)
		}
		return nil
	}

	// Otherwise use WriteCSV for single file output
	iter := ftdc.ReadChunks(ctx, f)

	var out *os.File
	if outputFile != "" {
		out, err = os.Create(outputFile)
		if err != nil {
			return fmt.Errorf("failed to create output file: %w", err)
		}
		defer out.Close()
	} else {
		out = os.Stdout
	}

	if err := ftdc.WriteCSV(ctx, iter, out); err != nil {
		return fmt.Errorf("failed to write CSV: %w", err)
	}

	return nil
}
