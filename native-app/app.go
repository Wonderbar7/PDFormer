package main

import (
	"context"
	"encoding/base64"
	"fmt"
	"os"

	"github.com/wailsapp/wails/v2/pkg/runtime"
)

// App struct
type App struct {
	ctx context.Context
}

// NewApp creates a new App application struct
func NewApp() *App {
	return &App{}
}

// startup is called when the app starts. The context is saved
// so we can call the runtime methods
func (a *App) startup(ctx context.Context) {
	a.ctx = ctx
}

// FileData represents the structure of the file being opened
type FileData struct {
	Name string `json:"name"`
	Data string `json:"data"`
	Path string `json:"path"`
}

// OpenFile opens a PDF file and returns its content as base64
func (a *App) OpenFile() (*FileData, error) {
	runtime.MessageDialog(a.ctx, runtime.MessageDialogOptions{
		Type:    runtime.InfoDialog,
		Title:   "Debug",
		Message: "Backend: OpenFile llamado",
	})
	runtime.LogInfo(a.ctx, "Abriendo diálogo de archivo...")
	selection, err := runtime.OpenFileDialog(a.ctx, runtime.OpenDialogOptions{
		Title: "Abrir Documento PDF",
		Filters: []runtime.FileFilter{
			{DisplayName: "Archivos PDF (*.pdf)", Pattern: "*.pdf"},
		},
	})

	if err != nil {
		return nil, err
	}

	if selection == "" {
		return nil, nil // Usuario canceló
	}

	data, err := os.ReadFile(selection)
	if err != nil {
		runtime.LogError(a.ctx, fmt.Sprintf("Error leyendo archivo: %v", err))
		return nil, fmt.Errorf("error leyendo archivo: %w", err)
	}

	info, err := os.Stat(selection)
	if err != nil {
		return nil, err
	}

	return &FileData{
		Name: info.Name(),
		Data: base64.StdEncoding.EncodeToString(data),
		Path: selection,
	}, nil
}

// SaveFile saves the PDF bytes to the disk
func (a *App) SaveFile(defaultName string, base64Data string) (string, error) {
	selection, err := runtime.SaveFileDialog(a.ctx, runtime.SaveDialogOptions{
		Title:           "Guardar Documento PDF",
		DefaultFilename: defaultName,
		Filters: []runtime.FileFilter{
			{DisplayName: "Archivos PDF (*.pdf)", Pattern: "*.pdf"},
		},
	})

	if err != nil {
		return "", err
	}

	if selection == "" {
		return "", nil // Usuario canceló
	}

	data, err := base64.StdEncoding.DecodeString(base64Data)
	if err != nil {
		return "", fmt.Errorf("error decodificando base64: %w", err)
	}

	err = os.WriteFile(selection, data, 0644)
	if err != nil {
		return "", fmt.Errorf("error guardando archivo: %w", err)
	}

	return selection, nil
}

// SaveFileDirect saves the PDF bytes directly to the given path
func (a *App) SaveFileDirect(path string, base64Data string) error {
	data, err := base64.StdEncoding.DecodeString(base64Data)
	if err != nil {
		return fmt.Errorf("error decodificando base64: %w", err)
	}

	err = os.WriteFile(path, data, 0644)
	if err != nil {
		return fmt.Errorf("error guardando archivo: %w", err)
	}

	return nil
}
